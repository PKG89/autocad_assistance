"""Input helpers for KML related workflows."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import List

import pandas as pd

logger = logging.getLogger(__name__)


_DELIMITER_CANDIDATES = ("\t", ";", ",", "|")

# Список кодировок для попытки чтения файла (в порядке приоритета)
_ENCODING_CANDIDATES = ["utf-8", "cp1251", "windows-1251", "latin1", "cp866", "utf-16"]



def _detect_delimiter(sample: str) -> str:
    for candidate in _DELIMITER_CANDIDATES:
        if candidate in sample:
            return candidate
    return " "



def to_float(value: str | float | int | None) -> float:
    """Конвертирует значение в float, игнорируя нечисловые символы."""
    if value is None:
        return 0.0
    text = str(value).strip().replace(",", ".")
    if text == "":
        return 0.0
    # Игнорируем символы разделителей и другие нечисловые символы (кроме точки и минуса)
    # Удаляем все символы, которые не являются цифрами, точкой, минусом или плюсом
    cleaned = "".join(c for c in text if c.isdigit() or c in ".-+eE")
    if cleaned == "" or cleaned == "-" or cleaned == "+":
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0



def _try_read_file_with_encodings(file_path: str, primary_encoding: str) -> tuple[str, str]:
    """
    Пытается прочитать файл с различными кодировками.
    Возвращает кортеж (кодировка, разделитель).
    """
    # Формируем список кодировок для попытки: сначала основная, потом остальные
    encodings_to_try = [primary_encoding]
    for enc in _ENCODING_CANDIDATES:
        if enc.lower() != primary_encoding.lower():
            encodings_to_try.append(enc)
    
    delimiter = None
    last_error = None
    
    # Пытаемся определить разделитель с разными кодировками
    # Проверяем несколько строк для более точного определения
    for enc in encodings_to_try:
        try:
            with open(file_path, "r", encoding=enc) as handle:
                delimiter_counts = {}
                lines_checked = 0
                max_lines_to_check = 10  # Проверяем до 10 строк
                
                for line in handle:
                    stripped = line.strip()
                    if stripped:
                        detected = _detect_delimiter(stripped)
                        delimiter_counts[detected] = delimiter_counts.get(detected, 0) + 1
                        lines_checked += 1
                        if lines_checked >= max_lines_to_check:
                            break
                
                # Выбираем разделитель, который встречается чаще всего
                if delimiter_counts:
                    delimiter = max(delimiter_counts.items(), key=lambda x: x[1])[0]
                    logger.debug("Определён разделитель '%s' с кодировкой '%s' (встречается в %d из %d строк)", 
                               delimiter, enc, delimiter_counts[delimiter], lines_checked)
                    return enc, delimiter
        except UnicodeDecodeError as e:
            last_error = e
            logger.debug("Не удалось прочитать файл с кодировкой '%s': %s", enc, e)
            continue
        except Exception as e:
            last_error = e
            logger.debug("Ошибка при чтении файла с кодировкой '%s': %s", enc, e)
            continue
    
    # Если не удалось определить разделитель, пробуем с errors='replace'
    for enc in encodings_to_try:
        try:
            with open(file_path, "r", encoding=enc, errors='replace') as handle:
                delimiter_counts = {}
                lines_checked = 0
                max_lines_to_check = 10
                
                for line in handle:
                    stripped = line.strip()
                    if stripped:
                        detected = _detect_delimiter(stripped)
                        delimiter_counts[detected] = delimiter_counts.get(detected, 0) + 1
                        lines_checked += 1
                        if lines_checked >= max_lines_to_check:
                            break
                
                if delimiter_counts:
                    delimiter = max(delimiter_counts.items(), key=lambda x: x[1])[0]
                    logger.warning("Использована кодировка '%s' с errors='replace', разделитель '%s'", enc, delimiter)
                    return enc, delimiter
        except Exception as e:
            last_error = e
            continue
    
    # Если ничего не помогло, выбрасываем последнюю ошибку
    if last_error:
        raise last_error
    raise ValueError(f"Не удалось прочитать файл {file_path} ни с одной из кодировок")


def load_kml_points(file_path: str, encoding: str) -> pd.DataFrame:
    """Load point data for KML generation from CSV/TSV/Excel sources."""
    ext = Path(file_path).suffix.lower()
    if ext in {".xlsx", ".xls"}:
        df_raw = pd.read_excel(file_path)
        if not df_raw.empty:
            first_row = df_raw.iloc[0]
            logger.debug("First Excel row: %s", first_row.tolist())
            first_row_str = [str(x).lower() for x in first_row.tolist()]
            if any(header in first_row_str for header in ["point", "x", "y", "h", "n"]):
                logger.debug("Detected header row in Excel input; skipping it")
                df_raw = df_raw.iloc[1:].reset_index(drop=True)
                logger.debug("Shape after header skip: %s", df_raw.shape)

        columns = list(df_raw.columns)
        while len(columns) < 5:
            columns.append(f"col_{len(columns)}")
        df_raw.columns = columns[: len(df_raw.columns)]
        point_col = columns[0]
        x_col = columns[1] if len(columns) > 1 else columns[0]
        y_col = columns[2] if len(columns) > 2 else columns[1]
        z_col = columns[3] if len(columns) > 3 else columns[2]
        comment_col = columns[4] if len(columns) > 4 else None
        df_raw["Point"] = df_raw[point_col].astype(str)
        df_raw["X"] = df_raw[x_col]
        df_raw["Y"] = df_raw[y_col]
        df_raw["Z"] = df_raw[z_col] if z_col in df_raw else 0
        if comment_col and comment_col in df_raw:
            df_raw["Comment"] = df_raw[comment_col].fillna("")
        else:
            df_raw["Comment"] = ""
        return df_raw[["Point", "X", "Y", "Z", "Comment"]]

    # Определяем кодировку и разделитель
    try:
        detected_encoding, delimiter = _try_read_file_with_encodings(file_path, encoding)
    except Exception as e:
        logger.exception("Ошибка при определении кодировки файла: %s", e)
        raise

    if not delimiter:
        delimiter = " "

    records: List[List[str]] = []
    # Пытаемся прочитать файл с определенной кодировкой
    try:
        with open(file_path, "r", encoding=detected_encoding) as handle:
            reader = csv.reader(handle, delimiter=delimiter, skipinitialspace=True)
            for row in reader:
                # Фильтруем токены: удаляем пустые строки и символы разделителей
                tokens = []
                for cell in row:
                    cleaned = cell.strip()
                    # Пропускаем пустые строки и символы разделителей
                    if cleaned and cleaned not in _DELIMITER_CANDIDATES:
                        tokens.append(cleaned)
                if len(tokens) < 2:
                    continue
                lowered = [token.lower() for token in tokens[:4]]
                logger.debug("Processing row: %s", tokens)
                logger.debug("Lowered tokens: %s", lowered)

                def is_number_like(text: str) -> bool:
                    try:
                        float(str(text).strip().replace(",", "."))
                        return True
                    except Exception:
                        return False

                non_numeric_count = 0
                alpha_present = False
                for token in tokens[:3]:
                    cleaned = str(token).strip()
                    if not is_number_like(cleaned):
                        non_numeric_count += 1
                        if any(ch.isalpha() for ch in cleaned):
                            alpha_present = True
                if non_numeric_count >= 2 and alpha_present:
                    logger.debug("Skipping header-like row: %s", tokens)
                    continue

                def is_integer_like(text: str) -> bool:
                    try:
                        int(str(text).strip())
                        return True
                    except Exception:
                        return False

                if len(tokens) >= 4 and is_integer_like(tokens[0]):
                    second = str(tokens[1]).strip()
                    if not is_number_like(second) or any(ch.isalpha() for ch in second):
                        logger.debug("Detected index column, shifting tokens: %s", tokens)
                        tokens = tokens[1:]

                point = tokens[0]
                x = tokens[1] if len(tokens) > 1 else "0"
                y = tokens[2] if len(tokens) > 2 else "0"
                z = tokens[3] if len(tokens) > 3 else "0"
                comment = " ".join(tokens[4:]) if len(tokens) > 4 else ""
                
                # Валидация: проверяем, что координаты можно преобразовать в числа
                # Если координаты не числовые, пропускаем строку
                try:
                    to_float(x)
                    to_float(y)
                    to_float(z)
                except (ValueError, TypeError):
                    logger.debug("Пропущена строка с нечисловыми координатами: %s", tokens)
                    continue
                
                records.append([point, x, y, z, comment])
    except UnicodeDecodeError:
        # Если все еще возникает ошибка, пробуем с errors='replace'
        logger.warning("Ошибка декодирования при чтении CSV, пробуем с errors='replace'")
        with open(file_path, "r", encoding=detected_encoding, errors='replace') as handle:
            reader = csv.reader(handle, delimiter=delimiter, skipinitialspace=True)
            for row in reader:
                # Фильтруем токены: удаляем пустые строки и символы разделителей
                tokens = []
                for cell in row:
                    cleaned = cell.strip()
                    # Пропускаем пустые строки и символы разделителей
                    if cleaned and cleaned not in _DELIMITER_CANDIDATES:
                        tokens.append(cleaned)
                if len(tokens) < 2:
                    continue
                lowered = [token.lower() for token in tokens[:4]]
                logger.debug("Processing row: %s", tokens)
                logger.debug("Lowered tokens: %s", lowered)

                def is_number_like(text: str) -> bool:
                    try:
                        float(str(text).strip().replace(",", "."))
                        return True
                    except Exception:
                        return False

                non_numeric_count = 0
                alpha_present = False
                for token in tokens[:3]:
                    cleaned = str(token).strip()
                    if not is_number_like(cleaned):
                        non_numeric_count += 1
                        if any(ch.isalpha() for ch in cleaned):
                            alpha_present = True
                if non_numeric_count >= 2 and alpha_present:
                    logger.debug("Skipping header-like row: %s", tokens)
                    continue

                def is_integer_like(text: str) -> bool:
                    try:
                        int(str(text).strip())
                        return True
                    except Exception:
                        return False

                if len(tokens) >= 4 and is_integer_like(tokens[0]):
                    second = str(tokens[1]).strip()
                    if not is_number_like(second) or any(ch.isalpha() for ch in second):
                        logger.debug("Detected index column, shifting tokens: %s", tokens)
                        tokens = tokens[1:]

                point = tokens[0]
                x = tokens[1] if len(tokens) > 1 else "0"
                y = tokens[2] if len(tokens) > 2 else "0"
                z = tokens[3] if len(tokens) > 3 else "0"
                comment = " ".join(tokens[4:]) if len(tokens) > 4 else ""
                
                # Валидация: проверяем, что координаты можно преобразовать в числа
                # Если координаты не числовые, пропускаем строку
                try:
                    to_float(x)
                    to_float(y)
                    to_float(z)
                except (ValueError, TypeError):
                    logger.debug("Пропущена строка с нечисловыми координатами: %s", tokens)
                    continue
                
                records.append([point, x, y, z, comment])

    df = pd.DataFrame(records, columns=["Point", "X", "Y", "Z", "Comment"])
    try:
        df["X"] = df["X"].apply(to_float).astype(float)
        df["Y"] = df["Y"].apply(to_float).astype(float)
        df["Z"] = df["Z"].apply(to_float).astype(float)
    except Exception:
        logger.exception("Cannot convert X/Y/Z values to float during KML load")
    return df

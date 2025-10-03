import streamlit as st
import pandas as pd
import pdfplumber
import re
import numpy as np
from collections import Counter
import math
import io
import base64

# =============================================================================
# CORE FUNCTIONS (simplified for Streamlit)
# =============================================================================

def get_font_weight(char):
    """Trích xuất độ đậm từ thông tin font của ký tự"""
    try:
        fontname = char.get('fontname', '')
        fontname_lower = fontname.lower()

        if any(keyword in fontname_lower for keyword in ['bold', 'black', 'heavy']):
            return 'Bold'
        elif any(keyword in fontname_lower for keyword in ['light', 'thin']):
            return 'Light'
        elif any(keyword in fontname_lower for keyword in ['medium', 'semi']):
            return 'Medium'
        else:
            return 'Regular'
    except Exception:
        return 'Unknown'

def calculate_advanced_metrics_with_rotation(group, number, x_pos, y_pos, orientation):
    """Tính toán 8 chỉ số khác biệt - XOAY SỐ TRƯỚC KHI TÍNH Font_Size, Char_Width, Char_Height"""
    try:
        metrics = {}
        is_vertical = (orientation == 'Vertical')

        # 1. Font Size (trung bình) - CHỈ TÍNH CHO KÝ TỰ SỐ
        font_sizes = [c.get('size', 0) for c in group if 'size' in c and c.get('text', '').isdigit()]
        if font_sizes:
            metrics['font_size'] = round(sum(font_sizes) / len(font_sizes), 1)
        else:
            metrics['font_size'] = 0.0

        # Kiểm tra loại bỏ Font_Size = 20.6
        if metrics['font_size'] == 20.6:
            return None

        # 2 & 3. Character Width và Height
        char_widths = []
        char_heights = []
        digit_chars = [c for c in group if c.get('text', '').isdigit()]

        for c in digit_chars:
            if 'x1' in c and 'x0' in c:
                width = c['x1'] - c['x0']
                char_widths.append(width)
            if 'bottom' in c and 'top' in c:
                height = abs(c['bottom'] - c['top'])
                char_heights.append(height)

        if char_widths and char_heights:
            avg_width = sum(char_widths) / len(char_widths)
            avg_height = sum(char_heights) / len(char_heights)

            if is_vertical:
                metrics['char_width'] = round(avg_height, 1)
                metrics['char_height'] = round(avg_width, 1)
            else:
                metrics['char_width'] = round(avg_width, 1)
                metrics['char_height'] = round(avg_height, 1)
        else:
            metrics['char_width'] = 0.0
            metrics['char_height'] = 0.0

        # 4. Density Score
        if metrics['char_width'] > 0 and metrics['char_height'] > 0:
            total_area = metrics['char_width'] * len(digit_chars) * metrics['char_height']
            if total_area > 0:
                metrics['density_score'] = round(len(digit_chars) / total_area * 1000, 2)
            else:
                metrics['density_score'] = 0.0
        else:
            metrics['density_score'] = 0.0

        # 5. Distance from Origin
        origin_distance = math.sqrt(x_pos**2 + y_pos**2)
        metrics['distance_from_origin'] = round(origin_distance, 1)

        # 6. Aspect Ratio
        if metrics['char_height'] > 0:
            total_width = metrics['char_width'] * len(digit_chars)
            aspect_ratio = total_width / metrics['char_height']
            metrics['aspect_ratio'] = round(aspect_ratio, 2)
        else:
            metrics['aspect_ratio'] = 0.0

        # 7. Character Spacing
        if len(digit_chars) > 1:
            spacings = []
            if is_vertical:
                sorted_chars = sorted(digit_chars, key=lambda c: c.get('top', 0))
                for i in range(len(sorted_chars) - 1):
                    current_char = sorted_chars[i]
                    next_char = sorted_chars[i + 1]
                    if 'bottom' in current_char and 'top' in next_char:
                        spacing = next_char['top'] - current_char['bottom']
                        spacings.append(abs(spacing))
            else:
                sorted_chars = sorted(digit_chars, key=lambda c: c.get('x0', 0))
                for i in range(len(sorted_chars) - 1):
                    current_char = sorted_chars[i]
                    next_char = sorted_chars[i + 1]
                    if 'x1' in current_char and 'x0' in next_char:
                        spacing = next_char['x0'] - current_char['x1']
                        spacings.append(abs(spacing))

            if spacings:
                metrics['char_spacing'] = round(sum(spacings) / len(spacings), 1)
            else:
                metrics['char_spacing'] = 0.0
        else:
            metrics['char_spacing'] = 0.0

        # 8. Text Angle
        if is_vertical:
            metrics['text_angle'] = 0.0
        else:
            if len(digit_chars) > 1:
                sorted_chars = sorted(digit_chars, key=lambda c: c.get('x0', 0))
                first_char = sorted_chars[0]
                last_char = sorted_chars[-1]
                delta_x = last_char.get('x0', 0) - first_char.get('x0', 0)
                delta_y = last_char.get('top', 0) - first_char.get('top', 0)
                if delta_x != 0:
                    angle_rad = math.atan2(delta_y, delta_x)
                    angle_deg = math.degrees(angle_rad)
                    metrics['text_angle'] = round(angle_deg, 1)
                else:
                    metrics['text_angle'] = 0.0
            else:
                metrics['text_angle'] = 0.0

        return metrics

    except Exception as e:
        return {
            'font_size': 0.0,
            'char_width': 0.0,
            'char_height': 0.0,
            'density_score': 0.0,
            'distance_from_origin': 0.0,
            'aspect_ratio': 0.0,
            'char_spacing': 0.0,
            'text_angle': 0.0
        }

def calculate_score_for_group(group_data):
    """Tính SCORE cho nhóm"""
    score = 0
    group_size = len(group_data)
    
    if group_size == 3:
        score += 30
    elif group_size == 5:
        score += 10

    char_spacings = group_data['Char_Spacing'].tolist()
    if len(char_spacings) > 1:
        max_spacing = max(char_spacings)
        min_spacing = min(char_spacings)
        spacing_diff = max_spacing - min_spacing
        if spacing_diff < 0.2:
            score += 10

    has_hv_mix = group_data['Has_HV_Mix'].iloc[0] if len(group_data) > 0 else False
    if has_hv_mix:
        score += 20

    return score

def get_font_priority(fontname):
    """Trả về độ ưu tiên của font"""
    if 'CIDFont+F3' in fontname or fontname == 'F3':
        return 4
    elif 'CIDFont+F2' in fontname or fontname == 'F2':
        return 3
    else:
        return 0

def determine_preferred_font_with_frequency_3(all_fonts, digit_chars):
    """Xác định font ưu tiên"""
    if not all_fonts:
        return None

    font_priorities = [(font, get_font_priority(font)) for font in all_fonts]
    valid_font_priorities = [(font, priority) for font, priority in font_priorities if priority > 0]

    if valid_font_priorities:
        font_char_counts = {}
        for char in digit_chars:
            fontname = char.get('fontname', 'Unknown')
            if char.get('size', 0) == 20.6:
                continue
            if fontname in [fp[0] for fp in valid_font_priorities]:
                if fontname not in font_char_counts:
                    font_char_counts[fontname] = []
                font_char_counts[fontname].append(char)

        total_valid_chars = sum(len(chars) for chars in font_char_counts.values())

        if total_valid_chars >= 3 and len(font_char_counts) >= 2:
            font_avg_positions = {}
            for fontname, chars in font_char_counts.items():
                avg_x = sum(c.get('x0', 0) for c in chars) / len(chars)
                avg_y = sum(c.get('top', 0) for c in chars) / len(chars)
                font_avg_positions[fontname] = (avg_x, avg_y)

            sorted_fonts = sorted(font_avg_positions.items(),
                                key=lambda x: (x[1][1], x[1][0]), reverse=True)
            return sorted_fonts[0][0]
        else:
            valid_font_priorities.sort(key=lambda x: x[1], reverse=True)
            return valid_font_priorities[0][0]
    else:
        font_frequencies = {}
        for char in digit_chars:
            if char.get('size', 0) == 20.6:
                continue
            fontname = char.get('fontname', 'Unknown')
            if fontname not in font_frequencies:
                font_frequencies[fontname] = 0
            font_frequencies[fontname] += 1

        fonts_with_freq_3 = [font for font, freq in font_frequencies.items() if freq == 3]

        if fonts_with_freq_3:
            if len(fonts_with_freq_3) == 1:
                return fonts_with_freq_3[0]
            else:
                font_avg_positions = {}
                for fontname in fonts_with_freq_3:
                    chars_of_font = [c for c in digit_chars if c.get('fontname', 'Unknown') == fontname and c.get('size', 0) != 20.6]
                    if chars_of_font:
                        avg_x = sum(c.get('x0', 0) for c in chars_of_font) / len(chars_of_font)
                        avg_y = sum(c.get('top', 0) for c in chars_of_font) / len(chars_of_font)
                        font_avg_positions[fontname] = (avg_x, avg_y)

                if font_avg_positions:
                    sorted_fonts = sorted(font_avg_positions.items(),
                                        key=lambda x: (x[1][1], x[1][0]), reverse=True)
                    return sorted_fonts[0][0]

        valid_fallback_fonts = {font: freq for font, freq in font_frequencies.items() if freq >= 3}
        if valid_fallback_fonts:
            return max(valid_fallback_fonts.items(), key=lambda x: x[1])[0]
        else:
            return None

def should_group_characters_for_all_numbers_with_decimals(base_char, other_char, current_group):
    """Xác định xem 2 ký tự có nên được nhóm lại không"""
    try:
        if base_char.get('size', 0) == 20.6 or other_char.get('size', 0) == 20.6:
            return False

        distance = math.sqrt(
            (base_char['x0'] - other_char['x0'])**2 +
            (base_char['top'] - other_char['top'])**2
        )

        if distance > 30:
            return False

        base_font = base_char.get('fontname', 'Unknown')
        other_font = other_char.get('fontname', 'Unknown')
        if base_font != other_font:
            if distance > 20:
                return False

        if len(current_group) > 1:
            group_x_span = max(c['x0'] for c in current_group) - min(c['x0'] for c in current_group)
            group_y_span = max(c['top'] for c in current_group) - min(c['top'] for c in current_group)

            is_group_vertical = group_y_span > group_x_span * 1.5

            if is_group_vertical:
                group_x_center = sum(c['x0'] for c in current_group) / len(current_group)
                if abs(other_char['x0'] - group_x_center) > 10:
                    return False
            else:
                group_y_center = sum(c['top'] for c in current_group) / len(current_group)
                if abs(other_char['top'] - group_y_center) > 8:
                    return False

        return True

    except Exception:
        return False

def create_character_groups_for_all_numbers_with_decimals(digit_and_dot_chars):
    """Tạo các nhóm ký tự cho TẤT CẢ số bao gồm số thập phân"""
    char_groups = []
    used_chars = set()

    valid_chars = [c for c in digit_and_dot_chars if c.get('size', 0) != 20.6]
    sorted_chars = sorted(valid_chars, key=lambda c: (c['top'], c['x0']))

    for i, base_char in enumerate(sorted_chars):
        if id(base_char) in used_chars:
            continue

        current_group = [base_char]
        used_chars.add(id(base_char))

        for j, other_char in enumerate(sorted_chars):
            if i == j or id(other_char) in used_chars:
                continue

            if should_group_characters_for_all_numbers_with_decimals(base_char, other_char, current_group):
                current_group.append(other_char)
                used_chars.add(id(other_char))

        if len(current_group) >= 1:
            char_groups.append(current_group)

    return char_groups

def process_character_group_for_all_numbers_with_decimals(group):
    """Xử lý nhóm ký tự cho TẤT CẢ số bao gồm số thập phân"""
    try:
        if len(group) < 2:
            return None

        if any(ch.get('size', 0) == 20.6 for ch in group):
            return None

        x_positions = [c['x0'] for c in group]
        y_positions = [c['top'] for c in group]

        x_span = max(x_positions) - min(x_positions)
        y_span = max(y_positions) - min(y_positions)

        is_vertical = y_span > x_span * 1.5

        if is_vertical:
            vertical_sorted = sorted(group, key=lambda c: c['top'], reverse=True)
            v_text = "".join([c['text'] for c in vertical_sorted])
        else:
            horizontal_sorted = sorted(group, key=lambda c: c['x0'])
            v_text = "".join([c['text'] for c in horizontal_sorted])

        if '.' in v_text:
            try:
                if v_text.count('.') == 1 and not v_text.startswith('.') and not v_text.endswith('.'):
                    num_value = float(v_text)
                    if 0.1 <= num_value <= 3500.0:
                        orientation = 'Vertical' if is_vertical else 'Horizontal'
                        return (num_value, orientation, True)
            except:
                pass
        else:
            try:
                num_value = int(v_text)
                if 0 < num_value <= 3500:
                    orientation = 'Vertical' if is_vertical else 'Horizontal'
                    return (num_value, orientation, False)
            except:
                pass

        return None

    except Exception:
        return None

def extract_all_valid_numbers_from_page(page):
    """BẢNG PHỤ: Trích xuất TẤT CẢ số hợp lệ"""
    all_valid_numbers = []

    try:
        chars = page.chars
        digit_and_dot_chars = [c for c in chars if c['text'].isdigit() or c['text'] == '.']

        if not digit_and_dot_chars:
            return all_valid_numbers

        char_groups = create_character_groups_for_all_numbers_with_decimals(digit_and_dot_chars)

        for group_idx, group in enumerate(char_groups):
            if len(group) == 1 and group[0]['text'].isdigit():
                try:
                    if group[0].get('size', 0) == 20.6:
                        continue

                    num_value = int(group[0]['text'])
                    fontname = group[0].get('fontname', 'Unknown')
                    font_weight = get_font_weight(group[0])
                    x_pos = group[0]['x0']
                    y_pos = group[0]['top']

                    if 0 < num_value <= 3500:
                        metrics = calculate_advanced_metrics_with_rotation(group, num_value, x_pos, y_pos, 'Single')

                        if metrics is None:
                            continue

                        all_valid_numbers.append({
                            'number': num_value,
                            'fontname': fontname,
                            'font_weight': font_weight,
                            'orientation': 'Single',
                            'x_pos': x_pos,
                            'y_pos': y_pos,
                            'chars_count': 1,
                            'font_size': metrics['font_size'],
                            'char_width': metrics['char_width'],
                            'char_height': metrics['char_height'],
                            'density_score': metrics['density_score'],
                            'distance_from_origin': metrics['distance_from_origin'],
                            'aspect_ratio': metrics['aspect_ratio'],
                            'char_spacing': metrics['char_spacing'],
                            'text_angle': metrics['text_angle']
                        })
                except:
                    continue
            else:
                result = process_character_group_for_all_numbers_with_decimals(group)
                if result:
                    number, orientation, is_decimal = result
                    if (is_decimal and 0.1 <= number <= 3500.0) or (not is_decimal and 0 < number <= 3500):
                        fonts = [ch.get("fontname", "Unknown") for ch in group]
                        fontname = Counter(fonts).most_common(1)[0][0] if fonts else "Unknown"

                        weights = [get_font_weight(ch) for ch in group]
                        weight_counter = Counter(weights)
                        common_weight = weight_counter.most_common(1)[0][0] if weights else "Unknown"

                        avg_x = sum(c['x0'] for c in group) / len(group)
                        avg_y = sum(c['top'] for c in group) / len(group)

                        metrics = calculate_advanced_metrics_with_rotation(group, number, avg_x, avg_y, orientation)

                        if metrics is None:
                            continue

                        all_valid_numbers.append({
                            'number': number,
                            'fontname': fontname,
                            'font_weight': common_weight,
                            'orientation': orientation,
                            'x_pos': avg_x,
                            'y_pos': avg_y,
                            'chars_count': len(group),
                            'font_size': metrics['font_size'],
                            'char_width': metrics['char_width'],
                            'char_height': metrics['char_height'],
                            'density_score': metrics['density_score'],
                            'distance_from_origin': metrics['distance_from_origin'],
                            'aspect_ratio': metrics['aspect_ratio'],
                            'char_spacing': metrics['char_spacing'],
                            'text_angle': metrics['text_angle']
                        })

        return all_valid_numbers

    except Exception as e:
        return all_valid_numbers

def expand_group_to_minimum_3_members(df):
    """Mở rộng group có 2 thành viên để đảm bảo có ít nhất 3 thành viên"""
    try:
        group_counts = df['Group'].value_counts()
        groups_with_2_numbers = [g for g in group_counts.index if group_counts[g] == 2 and g not in ['UNGROUPED', 'INSUFFICIENT_DATA', 'ERROR']]

        if not groups_with_2_numbers:
            return df

        for group_name in groups_with_2_numbers:
            group_data = df[df['Group'] == group_name]
            if len(group_data) != 2:
                continue

            group_font_names = group_data['Font Name'].unique()
            group_char_widths = group_data['Char_Width'].unique()
            group_char_heights = group_data['Char_Height'].tolist()

            if len(group_font_names) != 1 or len(group_char_widths) != 1:
                continue

            target_font_name = group_font_names[0]
            target_char_width = group_char_widths[0]

            candidate_data = df[df['Group'] != group_name]

            candidates = []
            for idx, row in candidate_data.iterrows():
                candidate_font_name = row['Font Name']
                candidate_char_width = row['Char_Width']
                candidate_char_height = row['Char_Height']
                candidate_font_size = row['Font_Size']

                if candidate_font_size == 20.6:
                    continue

                condition_1 = (candidate_font_name == target_font_name)
                condition_2 = (candidate_char_width == target_char_width)
                condition_3 = any(abs(candidate_char_height - gh) <= 0.2 for gh in group_char_heights)

                if condition_1 and condition_2 and condition_3:
                    candidates.append({
                        'index': idx,
                        'number': row['Valid Number'],
                        'current_group': row['Group']
                    })

            if candidates:
                selected_candidate = candidates[0]
                old_group = selected_candidate['current_group']

                df.loc[selected_candidate['index'], 'Group'] = group_name

                if old_group != 'UNGROUPED':
                    remaining_count = len(df[df['Group'] == old_group])
                    if remaining_count == 1:
                        last_number_idx = df[df['Group'] == old_group].index[0]
                        df.loc[last_number_idx, 'Group'] = 'UNGROUPED'
                        df.loc[last_number_idx, 'Has_HV_Mix'] = False

        return df

    except Exception as e:
        return df

def group_numbers_by_font_characteristics(df):
    """Phân nhóm số theo đặc tính font"""
    try:
        if len(df) < 1:
            df['Group'] = 'INSUFFICIENT_DATA'
            df['Has_HV_Mix'] = False
            return df

        df['Group'] = 'UNGROUPED'
        df['Has_HV_Mix'] = False
        group_counter = 1

        for i, row in df.iterrows():
            if df.loc[i, 'Group'] != 'UNGROUPED':
                continue

            current_font_size = row['Font_Size']
            current_char_width = row['Char_Width']
            current_char_height = row['Char_Height']
            current_orientation = row['Orientation']
            current_font_name = row['Font Name']

            if current_font_size == 20.6:
                continue

            group_indices = [i]

            for j, other_row in df.iterrows():
                if i == j or df.loc[j, 'Group'] != 'UNGROUPED':
                    continue

                other_font_size = other_row['Font_Size']
                other_char_width = other_row['Char_Width']
                other_char_height = other_row['Char_Height']
                other_orientation = other_row['Orientation']
                other_font_name = other_row['Font Name']

                if other_font_size == 20.6:
                    continue

                is_same_group = False

                if (current_font_size == other_font_size and
                    current_char_width == other_char_width and
                    current_char_height == other_char_height and
                    current_font_name == other_font_name):
                    is_same_group = True

                elif (current_font_name == other_font_name and
                      current_char_width == other_char_width and
                      current_font_size == other_font_size and
                      abs(current_char_height - other_char_height) <= 0.2):
                    is_same_group = True

                elif (current_font_name == other_font_name and
                      current_char_width == other_char_width and
                      current_font_size == other_font_size and
                      abs(current_char_height - other_char_height) <= 0.2):

                    orientations = {current_orientation, other_orientation}
                    if 'Single' in orientations and ('Horizontal' in orientations or 'Vertical' in orientations):
                        is_same_group = True

                elif (current_font_name == other_font_name and
                      current_char_width == other_char_width and
                      abs(current_char_height - other_char_height) <= 0.2):

                    if ((current_orientation == 'Horizontal' and other_orientation == 'Vertical') or
                        (current_orientation == 'Vertical' and other_orientation == 'Horizontal')):

                        vertical_row = row if current_orientation == 'Vertical' else other_row

                        if vertical_row['Font_Size'] == vertical_row['Char_Width']:
                            is_same_group = True

                if is_same_group:
                    group_indices.append(j)

            if len(group_indices) >= 1:
                group_name = f"GROUP_{group_counter}"
                for idx in group_indices:
                    df.loc[idx, 'Group'] = group_name

                if len(group_indices) > 1:
                    orientations_in_group = [df.loc[idx, 'Orientation'] for idx in group_indices]
                    unique_orientations = set(orientations_in_group)
                    if len(unique_orientations) > 1 and ('Horizontal' in unique_orientations or 'Vertical' in unique_orientations or 'Single' in unique_orientations):
                        for idx in group_indices:
                            df.loc[idx, 'Has_HV_Mix'] = True

                group_counter += 1

        df = expand_group_to_minimum_3_members(df)

        return df

    except Exception as e:
        df['Group'] = 'ERROR'
        df['Has_HV_Mix'] = False
        return df

def extract_foil_classification_with_detail(page):
    """Đếm FOIL/LIOF từ text đơn giản"""
    try:
        text = page.extract_text()
        if not text:
            return "", ""

        text_upper = text.upper()
        foil_count = text_upper.count('FOIL')
        liof_count = text_upper.count('LIOF')

        num_long = min(foil_count, 2)
        num_short = min(liof_count, 2)

        classification = ""
        if num_long > 0:
            classification += f"{num_long}L"
        if num_short > 0:
            classification += f"{num_short}S"

        detail_parts = []
        if foil_count > 0:
            detail_parts.append(f"{foil_count} FOIL")
        if liof_count > 0:
            detail_parts.append(f"{liof_count} LIOF")
        detail = ", ".join(detail_parts) if detail_parts else ""

        return classification if classification else "", detail

    except Exception as e:
        return "", ""

def extract_edgeband_classification_with_detail(page):
    """Đếm EDGEBAND/DNABEGDE từ text đơn giản"""
    try:
        text = page.extract_text()
        if not text:
            return "", ""

        text_upper = text.upper()
        edgeband_count = text_upper.count('EDGEBAND')
        dnabegde_count = text_upper.count('DNABEGDE')

        num_long = min(edgeband_count, 2)
        num_short = min(dnabegde_count, 2)

        classification = ""
        if num_long > 0:
            classification += f"{num_long}L"
        if num_short > 0:
            classification += f"{num_short}S"

        detail_parts = []
        if edgeband_count > 0:
            detail_parts.append(f"{edgeband_count} EDGEBAND")
        if dnabegde_count > 0:
            detail_parts.append(f"{dnabegde_count} DNABEGDE")
        detail = ", ".join(detail_parts) if detail_parts else ""

        return classification if classification else "", detail

    except Exception as e:
        return "", ""

def extract_laminate_classification_with_detail(page):
    """Trích xuất thông tin LAMINATE classification"""
    try:
        keywords = [
            "FLEX PAPER/PAPER",
            "GLUEABLE LAM",
            "GLUEABLE LAM/TC BLACK (IF APPLICABLE)",
            "LAM/MASKING (IF APPLICABLE)",
            "RAW",
            "LAM"
        ]

        lines = []
        page_text = page.extract_text()
        if page_text:
            for line_num, line in enumerate(page_text.split("\n"), start=1):
                lines.append((line_num, line.strip()))
        else:
            return "", ""

        all_found = []
        for idx, (line_num, line) in enumerate(lines):
            for kw in keywords:
                if kw in line:
                    all_found.append({
                        "Index": idx,
                        "Line": line_num,
                        "Keyword": kw,
                        "Text": line
                    })

        if len(all_found) >= 2:
            first_kw = all_found[0]["Keyword"]
            second_kw = all_found[1]["Keyword"]
            result = f"{first_kw}/{second_kw}"
            detail = f"Found: {first_kw} (line {all_found[0]['Line']}), {second_kw} (line {all_found[1]['Line']})"
            return result, detail
        elif len(all_found) == 1:
            return "", ""
        else:
            return "", ""

    except Exception as e:
        return "", ""

def extract_profile_from_page(page):
    """Trích xuất thông tin profile từ trang PDF"""
    try:
        text = page.extract_text()
        if not text:
            return ""

        profile_pattern = r"PROFILE:\s*([A-Z0-9\-]+)"
        match = re.search(profile_pattern, text, re.IGNORECASE)

        if match:
            return match.group(1).strip()

        lines = text.split('\n')
        for line in lines:
            if 'profile' in line.lower():
                profile_match = re.search(r'([A-Z0-9]+[A-Z]-[A-Z0-9]+)', line, re.IGNORECASE)
                if profile_match:
                    return profile_match.group(1).strip()

        return ""
    except Exception as e:
        return ""

def create_dimension_summary_with_score_priority(df, df_all_numbers):
    """Tạo bảng tóm tắt với logic mới"""
    if len(df) == 0:
        return pd.DataFrame(columns=["Drawing#", "Length (mm)", "Width (mm)", "Height (mm)", "Laminate", "FOIL", "EDGEBAND", "Profile"])

    # TÌM NHÓM CÓ SCORE CAO NHẤT VÀ ÍT NHẤT 3 THÀNH VIÊN
    if 'SCORE' in df_all_numbers.columns and len(df_all_numbers) > 0:
        group_sizes = df_all_numbers.groupby('Group').size()
        valid_groups = group_sizes[group_sizes >= 3].index.tolist()
        
        if valid_groups:
            group_scores = df_all_numbers[df_all_numbers['Group'].isin(valid_groups)].groupby('Group')['SCORE'].first().sort_values(ascending=False)

            if len(group_scores) > 0:
                highest_score_group = group_scores.index[0]
                high_score_group_data = df_all_numbers[df_all_numbers['Group'] == highest_score_group]
                high_score_numbers = high_score_group_data['Valid Number'].tolist()
                unique_numbers = sorted(list(set(high_score_numbers)), reverse=True)
            else:
                all_numbers = df['Number_Int'].tolist()
                unique_numbers = sorted(list(set(all_numbers)), reverse=True)
        else:
            all_numbers = df['Number_Int'].tolist()
            unique_numbers = sorted(list(set(all_numbers)), reverse=True)
    else:
        all_numbers = df['Number_Int'].tolist()
        unique_numbers = sorted(list(set(all_numbers)), reverse=True)

    # LOGIC DIMENSION TIÊU CHUẨN
    length_number = ""
    width_number = ""
    height_number = ""

    if len(unique_numbers) == 1:
        length_number = str(unique_numbers[0])
        width_number = str(unique_numbers[0])
        height_number = str(unique_numbers[0])
    elif len(unique_numbers) == 2:
        length_number = str(unique_numbers[0])
        width_number = str(unique_numbers[1])
        height_number = str(unique_numbers[1])
    elif len(unique_numbers) >= 3:
        length_number = str(unique_numbers[0])
        width_number = str(unique_numbers[-2])
        height_number = str(unique_numbers[-1])

    # Lấy filename
    filename = df.iloc[0]['File']
    drawing_name = filename.replace('.pdf', '') if filename.endswith('.pdf') else filename

    # Lấy thông tin profile, FOIL, EDGEBAND, LAMINATE
    profile_info = df.iloc[0]['Profile'] if 'Profile' in df.columns else ""
    foil_info = df.iloc[0]['FOIL'] if 'FOIL' in df.columns else ""
    edgeband_info = df.iloc[0]['EDGEBAND'] if 'EDGEBAND' in df.columns else ""
    laminate_info = df.iloc[0]['Laminate'] if 'Laminate' in df.columns else ""

    result_df = pd.DataFrame({
        "Drawing#": [drawing_name],
        "Length (mm)": [length_number],
        "Width (mm)": [width_number],
        "Height (mm)": [height_number],
        "Laminate": [laminate_info],
        "FOIL": [foil_info],
        "EDGEBAND": [edgeband_info],
        "Profile": [profile_info]
    })

    return result_df

def process_pdf_file(uploaded_file):
    """Xử lý file PDF và trả về bảng chính"""
    try:
        # Đọc file PDF
        with pdfplumber.open(uploaded_file) as pdf:
            if len(pdf.pages) == 0:
                return pd.DataFrame()

            page = pdf.pages[0]
            
            # Trích xuất thông tin
            profile_info = extract_profile_from_page(page)
            foil_classification, _ = extract_foil_classification_with_detail(page)
            edgeband_classification, _ = extract_edgeband_classification_with_detail(page)
            laminate_classification, _ = extract_laminate_classification_with_detail(page)
            
            # Trích xuất tất cả số hợp lệ
            all_valid_numbers = extract_all_valid_numbers_from_page(page)
            
            if not all_valid_numbers:
                return pd.DataFrame()

            # Tạo DataFrame cho bảng phụ
            file_secondary_results = []
            for i, number_info in enumerate(all_valid_numbers):
                file_secondary_results.append({
                    "File": uploaded_file.name,
                    "Valid Number": number_info['number'],
                    "Font Name": number_info['fontname'],
                    "Font Weight": number_info['font_weight'],
                    "Orientation": number_info['orientation'],
                    "Position_X": round(number_info['x_pos'], 1),
                    "Position_Y": round(number_info['y_pos'], 1),
                    "Chars_Count": number_info['chars_count'],
                    "Font_Size": number_info['font_size'],
                    "Char_Width": number_info['char_width'],
                    "Char_Height": number_info['char_height'],
                    "Density_Score": number_info['density_score'],
                    "Distance_Origin": number_info['distance_from_origin'],
                    "Aspect_Ratio": number_info['aspect_ratio'],
                    "Char_Spacing": number_info['char_spacing'],
                    "Text_Angle": number_info['text_angle'],
                    "Index": i+1
                })

            if not file_secondary_results:
                return pd.DataFrame()

            df_file_secondary = pd.DataFrame(file_secondary_results)
            
            # Phân nhóm và tính score
            df_file_secondary = group_numbers_by_font_characteristics(df_file_secondary)
            
            # Tính SCORE cho từng GROUP
            df_file_secondary['SCORE'] = 0
            for group_name in df_file_secondary['Group'].unique():
                if group_name not in ['UNGROUPED', 'INSUFFICIENT_DATA', 'ERROR']:
                    group_data = df_file_secondary[df_file_secondary['Group'] == group_name]
                    score = calculate_score_for_group(group_data)
                    df_file_secondary.loc[df_file_secondary['Group'] == group_name, 'SCORE'] = score

            # Tạo bảng chính dummy
            df_main_dummy = pd.DataFrame([{
                "File": uploaded_file.name,
                "Number_Int": 0,
                "Profile": profile_info,
                "FOIL": foil_classification,
                "EDGEBAND": edgeband_classification,
                "Laminate": laminate_classification
            }])

            # Tạo bảng tóm tắt
            summary = create_dimension_summary_with_score_priority(df_main_dummy, df_file_secondary)
            
            return summary

    except Exception as e:
        st.error(f"Lỗi khi xử lý file: {str(e)}")
        return pd.DataFrame()

def create_download_link(df, filename):
    """Tạo link download Excel"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Results')
    
    excel_data = output.getvalue()
    b64 = base64.b64encode(excel_data).decode()
    
    return f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">Download Excel File</a>'

# =============================================================================
# STREAMLIT APP
# =============================================================================

def main():
    st.set_page_config(page_title="PDF Processor", layout="wide")
    st.title("PDF Processor")
    
    # File uploader
    uploaded_files = st.file_uploader(
        "Choose PDF files",
        type="pdf",
        accept_multiple_files=True,
        help="Select one or more PDF files to process"
    )
    
    if uploaded_files:
        all_results = []
        
        # Progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, uploaded_file in enumerate(uploaded_files):
            status_text.text(f'Processing {uploaded_file.name}...')
            progress_bar.progress((i + 1) / len(uploaded_files))
            
            result_df = process_pdf_file(uploaded_file)
            if not result_df.empty:
                all_results.append(result_df)
        
        status_text.text('Processing complete!')
        
        if all_results:
            # Combine all results
            final_summary = pd.concat(all_results, ignore_index=True)
            
            # Display results
            st.subheader("Results")
            st.dataframe(final_summary, use_container_width=True)
            
            # Download button
            if not final_summary.empty:
                excel_link = create_download_link(final_summary, "pdf_processing_results.xlsx")
                st.markdown(excel_link, unsafe_allow_html=True)
        else:
            st.warning("No results found in the uploaded files.")

if __name__ == "__main__":
    main()

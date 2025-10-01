import streamlit as st
import pdfplumber
import pandas as pd
import re
import numpy as np
from collections import Counter
import math
import io

# =============================================================================
# ENHANCED NUMBER EXTRACTION - XOAY SỐ TRƯỚC KHI TÍNH METRICS
# =============================================================================

def reverse_number_string(number_string):
    """Đảo ngược chuỗi số"""
    return number_string[::-1]

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
    """Tính toán 8 chỉ số khác biệt - XOAY SỐ TRƯỚC KHI TÍNH Font_Size, Char_Width, Char_Height - CHỈ TÍNH SỐ"""
    try:
        metrics = {}
        is_vertical = (orientation == 'Vertical')

        # 1. Font Size (trung bình) - CHỈ TÍNH CHO KÝ TỰ SỐ
        font_sizes = [c.get('size', 0) for c in group if 'size' in c and c.get('text', '').isdigit()]
        if font_sizes:
            metrics['font_size'] = round(sum(font_sizes) / len(font_sizes), 1)
        else:
            metrics['font_size'] = 0.0

        # 2 & 3. Character Width và Height - CHỈ TÍNH CHO KÝ TỰ SỐ - XOAY NẾU LÀ SỐ DỌC
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
    """Tính SCORE cho nhóm theo các tiêu chí"""
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

def check_grain_exists_in_page(page):
    """Kiểm tra xem trang có chứa chữ GRAIN/NIARG không"""
    try:
        text = page.extract_text()
        if not text:
            return False

        text_upper = text.upper()
        has_grain = 'GRAIN' in text_upper or 'NIARG' in text_upper
        return has_grain

    except Exception as e:
        return False

def extract_laminate_classification_with_detail(page):
    """Trích xuất thông tin Laminate classification"""
    try:
        keywords = [
            "FLEX PAPER/PAPER",
            "GLUEABLE LAM",
            "MAL ELBAEULG",
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

def find_grain_sequence_with_direction(candidate_chars):
    """Tìm chuỗi GRAIN/NIARG và xác định hướng dựa trên layout của text"""
    try:
        char_groups = {}
        for char_info in candidate_chars:
            char_type = char_info['char']
            if char_type not in char_groups:
                char_groups[char_type] = []
            char_groups[char_type].append(char_info)

        required_chars = ['G', 'R', 'A', 'I', 'N']
        for required_char in required_chars:
            if required_char not in char_groups or len(char_groups[required_char]) == 0:
                return None

        representative_chars = {}
        for char_type in required_chars:
            closest_char = min(char_groups[char_type], key=lambda c: c['distance'])
            representative_chars[char_type] = closest_char

        char_positions = [(char_type, char_info['x'], char_info['y'])
                         for char_type, char_info in representative_chars.items()]

        x_positions = [pos[1] for pos in char_positions]
        y_positions = [pos[2] for pos in char_positions]

        x_span = max(x_positions) - min(x_positions)
        y_span = max(y_positions) - min(y_positions)

        if x_span > y_span * 1.5:
            text_direction = "Horizontal"
        elif y_span > x_span * 1.5:
            text_direction = "Vertical"
        else:
            text_direction = "Horizontal"

        sequence_type = determine_grain_vs_niarg(representative_chars, text_direction)

        return {
            'type': sequence_type,
            'direction': text_direction
        }

    except Exception as e:
        return None

def determine_grain_vs_niarg(representative_chars, text_direction):
    """Xác định thứ tự đọc GRAIN hay NIARG dựa trên layout"""
    try:
        if text_direction == "Horizontal":
            sorted_items = sorted(representative_chars.items(), key=lambda x: x[1]['x'])
        else:
            sorted_items = sorted(representative_chars.items(), key=lambda x: x[1]['y'])

        sequence = "".join([char_type for char_type, char_info in sorted_items])

        if "GRAIN" in sequence:
            return "GRAIN"
        elif "NIARG" in sequence:
            return "NIARG"
        else:
            grain_score = calculate_sequence_similarity(sequence, "GRAIN")
            niarg_score = calculate_sequence_similarity(sequence, "NIARG")

            if grain_score >= niarg_score:
                return "GRAIN"
            else:
                return "NIARG"

    except Exception as e:
        return "GRAIN"

def calculate_sequence_similarity(actual_sequence, target_sequence):
    """Tính điểm tương đồng giữa 2 chuỗi"""
    try:
        score = 0
        min_len = min(len(actual_sequence), len(target_sequence))

        for i in range(min_len):
            if actual_sequence[i] == target_sequence[i]:
                score += 1

        return score
    except:
        return 0

def search_grain_text_for_group_by_priority(page, group_data, search_distance=200):
    """Tìm GRAIN cho group"""
    try:
        if not check_grain_exists_in_page(page):
            return None, ""

        sorted_group = group_data.sort_values('Valid Number', ascending=False)

        for idx, row in sorted_group.iterrows():
            num_value = row['Valid Number']
            num_x = row['Position_X']
            num_y = row['Position_Y']
            num_orientation = row['Orientation']

            grain_result = search_grain_along_axis(page, num_x, num_y, num_orientation, search_distance)

            if grain_result:
                return idx, grain_result
            else:
                grain_result = search_grain_in_square_area(page, num_x, num_y, search_distance)
                if grain_result:
                    return idx, grain_result

        return None, ""

    except Exception as e:
        return None, ""

def search_grain_along_axis(page, num_x, num_y, num_orientation, search_distance=200):
    """Tìm GRAIN/NIARG theo trục"""
    try:
        chars = page.chars
        if not chars:
            return ""

        if num_orientation == 'Horizontal':
            search_axis = 'vertical'
        elif num_orientation == 'Vertical':
            search_axis = 'horizontal'
        else:
            search_axis = 'both'

        text_chars = [c for c in chars if c.get('text', '').isalpha()]
        candidate_chars = []

        for char in text_chars:
            char_x = char.get('x0', 0)
            char_y = char.get('top', 0)
            char_text = char.get('text', '').upper()

            on_axis = False

            if search_axis == 'horizontal':
                if (abs(char_y - num_y) <= 20 and abs(char_x - num_x) <= search_distance):
                    on_axis = True
            elif search_axis == 'vertical':
                if (abs(char_x - num_x) <= 20 and abs(char_y - num_y) <= search_distance):
                    on_axis = True
            elif search_axis == 'both':
                if ((abs(char_y - num_y) <= 20 and abs(char_x - num_x) <= search_distance) or
                    (abs(char_x - num_x) <= 20 and abs(char_y - num_y) <= search_distance)):
                    on_axis = True

            if on_axis and char_text in ['G', 'R', 'A', 'I', 'N']:
                candidate_chars.append({
                    'char': char_text,
                    'x': char_x,
                    'y': char_y,
                    'distance': math.sqrt((char_x - num_x)**2 + (char_y - num_y)**2),
                    'original_char': char
                })

        candidate_chars.sort(key=lambda c: c['distance'])

        if len(candidate_chars) >= 5:
            grain_sequence_info = find_grain_sequence_with_direction(candidate_chars)

            if grain_sequence_info:
                sequence_type = grain_sequence_info['type']

                if sequence_type == "GRAIN":
                    result = "Horizontal"
                elif sequence_type == "NIARG":
                    result = "Vertical"
                else:
                    result = "Horizontal"

                return result

        return ""

    except Exception as e:
        return ""

def search_grain_in_square_area(page, num_x, num_y, search_distance=200):
    """Tìm GRAIN/NIARG trong phạm vi hình vuông quanh number"""
    try:
        chars = page.chars
        if not chars:
            return ""

        text_chars = [c for c in chars if c.get('text', '').isalpha()]
        candidate_chars = []

        for char in text_chars:
            char_x = char.get('x0', 0)
            char_y = char.get('top', 0)
            char_text = char.get('text', '').upper()

            if (abs(char_x - num_x) <= search_distance and
                abs(char_y - num_y) <= search_distance and
                char_text in ['G', 'R', 'A', 'I', 'N']):

                candidate_chars.append({
                    'char': char_text,
                    'x': char_x,
                    'y': char_y,
                    'distance': math.sqrt((char_x - num_x)**2 + (char_y - num_y)**2),
                    'original_char': char
                })

        candidate_chars.sort(key=lambda c: c['distance'])

        if len(candidate_chars) >= 5:
            grain_sequence_info = find_grain_sequence_with_direction(candidate_chars)

            if grain_sequence_info:
                sequence_type = grain_sequence_info['type']

                if sequence_type == "GRAIN":
                    result = "Horizontal"
                elif sequence_type == "NIARG":
                    result = "Vertical"
                else:
                    result = "Horizontal"

                return result

        return ""

    except Exception as e:
        return ""

def expand_small_groups(df):
    """Mở rộng các nhóm chỉ có 2 số"""
    try:
        group_counts = df['Group'].value_counts()
        groups_with_2_numbers = group_counts[group_counts == 2].index.tolist()

        if not groups_with_2_numbers:
            return df

        for group_name in groups_with_2_numbers:
            group_data = df[df['Group'] == group_name]
            if len(group_data) != 2:
                continue

            group_char_widths = group_data['Char_Width'].unique()
            if len(group_char_widths) != 1:
                continue

            target_char_width = group_char_widths[0]
            group_char_heights = group_data['Char_Height'].tolist()
            group_font_names = group_data['Font Name'].unique()
            group_orientations = set(group_data['Orientation'].tolist())

            candidate_data = df[df['Group'] != group_name]

            candidates = []
            for idx, row in candidate_data.iterrows():
                candidate_font_size = row['Font_Size']
                candidate_char_width = row['Char_Width']
                candidate_char_height = row['Char_Height']
                candidate_font_name = row['Font Name']
                candidate_orientation = row['Orientation']
                candidate_current_group = row['Group']

                condition_1 = (candidate_font_size == candidate_char_width)
                condition_2 = (candidate_char_width == target_char_width)
                condition_3 = any(abs(candidate_char_height - gh) <= 0.2 for gh in group_char_heights)
                condition_4 = (candidate_font_name in group_font_names)

                condition_5 = True
                if candidate_orientation == 'Single':
                    condition_5 = True
                elif candidate_orientation in ['Horizontal', 'Vertical']:
                    new_orientations = group_orientations | {candidate_orientation}
                    if len(new_orientations) > len(group_orientations):
                        condition_5 = True
                    else:
                        condition_5 = False

                if condition_1 and condition_2 and condition_3 and condition_4 and condition_5:
                    candidates.append({
                        'index': idx,
                        'number': row['Valid Number'],
                        'orientation': candidate_orientation,
                        'current_group': candidate_current_group
                    })

            if candidates:
                groups_to_check_empty = set()

                for candidate in candidates:
                    old_group = candidate['current_group']
                    if old_group != 'UNGROUPED':
                        groups_to_check_empty.add(old_group)

                    df.loc[candidate['index'], 'Group'] = group_name
                    df.loc[candidate['index'], 'Has_HV_Mix'] = True

                df.loc[df['Group'] == group_name, 'Has_HV_Mix'] = True

                for old_group in groups_to_check_empty:
                    remaining_count = len(df[df['Group'] == old_group])
                    if remaining_count == 1:
                        last_number_idx = df[df['Group'] == old_group].index[0]
                        df.loc[last_number_idx, 'Group'] = 'UNGROUPED'
                        df.loc[last_number_idx, 'Has_HV_Mix'] = False

        return df

    except Exception as e:
        return df

def check_uniform_metrics_for_has_hv_mix(group_data):
    """Kiểm tra xem tất cả số trong group có cùng Font_Size, Char_Width, Char_Height không"""
    try:
        if len(group_data) <= 1:
            return True

        font_sizes = group_data['Font_Size'].unique()
        char_widths = group_data['Char_Width'].unique()
        char_heights = group_data['Char_Height'].unique()

        uniform_font_size = len(font_sizes) == 1
        uniform_char_width = len(char_widths) == 1
        uniform_char_height = len(char_heights) == 1

        is_uniform = uniform_font_size and uniform_char_width and uniform_char_height

        return is_uniform

    except Exception as e:
        return False

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

            group_indices = [i]

            for j, other_row in df.iterrows():
                if i == j or df.loc[j, 'Group'] != 'UNGROUPED':
                    continue

                other_font_size = other_row['Font_Size']
                other_char_width = other_row['Char_Width']
                other_char_height = other_row['Char_Height']
                other_orientation = other_row['Orientation']
                other_font_name = other_row['Font Name']

                is_same_group = False

                # ĐIỀU KIỆN 1: Hoàn toàn giống nhau
                if (current_font_size == other_font_size and
                    current_char_width == other_char_width and
                    current_char_height == other_char_height and
                    current_orientation == other_orientation and
                    current_font_name == other_font_name):
                    is_same_group = True

                # ĐIỀU KIỆN 2: Chênh lệch Char_Height ≤ 0.2 + cùng các đặc tính khác
                elif (current_font_name == other_font_name and
                      current_char_width == other_char_width and
                      current_orientation == other_orientation and
                      current_font_size == other_font_size and
                      abs(current_char_height - other_char_height) <= 0.2):
                    is_same_group = True

                # ĐIỀU KIỆN 3: Single orientation với H/V có cùng đặc tính font
                elif (current_font_name == other_font_name and
                      current_char_width == other_char_width and
                      current_font_size == other_font_size and
                      abs(current_char_height - other_char_height) <= 0.2):

                    orientations = {current_orientation, other_orientation}
                    if 'Single' in orientations and ('Horizontal' in orientations or 'Vertical' in orientations):
                        is_same_group = True

                # ĐIỀU KIỆN 4: Trường hợp đặc biệt Horizontal/Vertical mix
                elif (current_font_name == other_font_name and
                      current_char_width == other_char_width and
                      abs(current_char_height - other_char_height) <= 0.2):

                    if ((current_orientation == 'Horizontal' and other_orientation == 'Vertical') or
                        (current_orientation == 'Vertical' and other_orientation == 'Horizontal')):

                        horizontal_row = row if current_orientation == 'Horizontal' else other_row
                        vertical_row = other_row if current_orientation == 'Horizontal' else row

                        if vertical_row['Font_Size'] == vertical_row['Char_Width']:
                            is_same_group = True

                if is_same_group:
                    group_indices.append(j)

            if len(group_indices) >= 1:
                group_name = f"GROUP_{group_counter}"
                for idx in group_indices:
                    df.loc[idx, 'Group'] = group_name

                if len(group_indices) > 1:
                    numbers_in_group = [df.loc[idx, 'Valid Number'] for idx in group_indices]
                    orientations_in_group = [df.loc[idx, 'Orientation'] for idx in group_indices]

                    group_data = df[df['Group'] == group_name]
                    is_uniform = check_uniform_metrics_for_has_hv_mix(group_data)

                    if is_uniform:
                        for idx in group_indices:
                            df.loc[idx, 'Has_HV_Mix'] = False
                    else:
                        unique_orientations = set(orientations_in_group)
                        if len(unique_orientations) > 1 and ('Horizontal' in unique_orientations or 'Vertical' in unique_orientations or 'Single' in unique_orientations):
                            for idx in group_indices:
                                df.loc[idx, 'Has_HV_Mix'] = True

                group_counter += 1

        df = expand_small_groups(df)

        for group_name in df['Group'].unique():
            if group_name not in ['UNGROUPED', 'INSUFFICIENT_DATA', 'ERROR']:
                group_data = df[df['Group'] == group_name]
                if len(group_data) > 1:
                    is_uniform = check_uniform_metrics_for_has_hv_mix(group_data)
                    if is_uniform:
                        df.loc[df['Group'] == group_name, 'Has_HV_Mix'] = False

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

        detail_parts = []
        if foil_count > 0:
            detail_parts.append(f"{foil_count} FOIL")
        if liof_count > 0:
            detail_parts.append(f"{liof_count} LIOF")

        detail = ", ".join(detail_parts) if detail_parts else ""

        num_long = min(foil_count, 2)
        num_short = min(liof_count, 2)

        classification = ""
        if num_long > 0:
            classification += f"{num_long}L"
        if num_short > 0:
            classification += f"{num_short}S"

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

        detail_parts = []
        if edgeband_count > 0:
            detail_parts.append(f"{edgeband_count} EDGEBAND")
        if dnabegde_count > 0:
            detail_parts.append(f"{dnabegde_count} DNABEGDE")

        detail = ", ".join(detail_parts) if detail_parts else ""

        num_long = min(edgeband_count, 2)
        num_short = min(dnabegde_count, 2)

        classification = ""
        if num_long > 0:
            classification += f"{num_long}L"
        if num_short > 0:
            classification += f"{num_short}S"

        return classification if classification else "", detail

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

def is_valid_font(fontname):
    """Kiểm tra font name có hợp lệ không"""
    valid_fonts = ['CIDFont+F3', 'CIDFont+F2', 'F3', 'F2']
    return fontname in valid_fonts or any(fontname.endswith(f) for f in valid_fonts)

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

            selected_font = sorted_fonts[0][0]
            return selected_font
        else:
            valid_font_priorities.sort(key=lambda x: x[1], reverse=True)
            selected_font = valid_font_priorities[0][0]
            return selected_font
    else:
        font_frequencies = {}
        for char in digit_chars:
            fontname = char.get('fontname', 'Unknown')
            if fontname not in font_frequencies:
                font_frequencies[fontname] = 0
            font_frequencies[fontname] += 1

        fonts_with_freq_3 = [font for font, freq in font_frequencies.items() if freq == 3]

        if fonts_with_freq_3:
            if len(fonts_with_freq_3) == 1:
                selected_font = fonts_with_freq_3[0]
                return selected_font
            else:
                font_avg_positions = {}
                for fontname in fonts_with_freq_3:
                    chars_of_font = [c for c in digit_chars if c.get('fontname', 'Unknown') == fontname]
                    if chars_of_font:
                        avg_x = sum(c.get('x0', 0) for c in chars_of_font) / len(chars_of_font)
                        avg_y = sum(c.get('top', 0) for c in chars_of_font) / len(chars_of_font)
                        font_avg_positions[fontname] = (avg_x, avg_y)

                if font_avg_positions:
                    sorted_fonts = sorted(font_avg_positions.items(),
                                        key=lambda x: (x[1][1], x[1][0]), reverse=True)
                    selected_font = sorted_fonts[0][0]
                    return selected_font

        valid_fallback_fonts = {font: freq for font, freq in font_frequencies.items() if freq >= 3}

        if valid_fallback_fonts:
            selected_font = max(valid_fallback_fonts.items(), key=lambda x: x[1])[0]
            return selected_font
        else:
            return None

def extract_numbers_and_decimals_from_chars(page):
    """Trích xuất số và số thập phân"""
    numbers = []
    orientations = {}
    font_info = {}

    try:
        chars = page.chars
        digit_and_dot_chars = [c for c in chars if c['text'].isdigit() or c['text'] == '.']

        if not digit_and_dot_chars:
            return numbers, orientations, font_info

        all_fonts = list(set([c.get('fontname', 'Unknown') for c in digit_and_dot_chars]))
        preferred_font = determine_preferred_font_with_frequency_3(all_fonts, digit_and_dot_chars)

        if not preferred_font:
            return numbers, orientations, font_info

        char_groups = create_character_groups_with_decimals(digit_and_dot_chars, preferred_font)
        extracted_numbers = []

        for group in char_groups:
            if len(group) == 1 and group[0]['text'].isdigit():
                try:
                    num_value = int(group[0]['text'])
                    fontname = group[0].get('fontname', 'Unknown')
                    font_weight = get_font_weight(group[0])

                    if (1 <= num_value <= 3500 and fontname == preferred_font):
                        numbers.append(num_value)
                        orientations[f"{num_value}_{len(numbers)}"] = 'Single'
                        font_info[f"{num_value}_{len(numbers)}"] = {
                            'chars': group,
                            'fontname': fontname,
                            'font_weight': font_weight,
                            'value': num_value
                        }
                        extracted_numbers.append(num_value)
                except:
                    continue
            else:
                result = process_character_group_with_decimals(group, extracted_numbers, preferred_font)
                if result:
                    number, orientation, is_decimal = result

                    if is_decimal:
                        numbers.append(number)
                    else:
                        numbers.append(int(number))

                    orientations[f"{number}_{len(numbers)}"] = orientation
                    fonts = [ch.get("fontname", "Unknown") for ch in group]
                    fontname = Counter(fonts).most_common(1)[0][0] if fonts else "Unknown"

                    weights = [get_font_weight(ch) for ch in group]
                    weight_counter = Counter(weights)
                    common_weight = weight_counter.most_common(1)[0][0] if weights else "Unknown"

                    font_info[f"{number}_{len(numbers)}"] = {
                        'chars': group,
                        'fontname': fontname,
                        'font_weight': common_weight,
                        'value': number
                    }
                    extracted_numbers.append(number)

    except Exception as e:
        pass

    return numbers, orientations, font_info

def create_character_groups_with_decimals(digit_and_dot_chars, preferred_font):
    """Tạo các nhóm ký tự bao gồm số và dấu chấm thập phân"""
    char_groups = []
    used_chars = set()

    valid_chars = [c for c in digit_and_dot_chars if c.get('fontname', 'Unknown') == preferred_font]

    if not valid_chars:
        return char_groups

    sorted_chars = sorted(valid_chars, key=lambda c: (c['top'], c['x0']))

    for i, base_char in enumerate(sorted_chars):
        if id(base_char) in used_chars:
            continue

        current_group = [base_char]
        used_chars.add(id(base_char))

        for j, other_char in enumerate(sorted_chars):
            if i == j or id(other_char) in used_chars:
                continue

            if should_group_characters_with_decimals(base_char, other_char, current_group, preferred_font):
                current_group.append(other_char)
                used_chars.add(id(other_char))

        if len(current_group) >= 1:
            char_groups.append(current_group)

    return char_groups

def should_group_characters_with_decimals(base_char, other_char, current_group, preferred_font):
    """Xác định xem 2 ký tự có nên được nhóm lại không"""
    try:
        base_font = base_char.get('fontname', 'Unknown')
        other_font = other_char.get('fontname', 'Unknown')

        if not (base_font == preferred_font and other_font == preferred_font):
            return False

        distance = math.sqrt(
            (base_char['x0'] - other_char['x0'])**2 +
            (base_char['top'] - other_char['top'])**2
        )

        if distance > 30:
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

def process_character_group_with_decimals(group, extracted_numbers, preferred_font):
    """Xử lý nhóm ký tự bao gồm số thập phân"""
    try:
        if len(group) < 1:
            return None

        fonts = [ch.get("fontname", "Unknown") for ch in group]
        if not all(font == preferred_font for font in fonts):
            return None

        if len(group) == 1:
            char_text = group[0]['text']
            if char_text.isdigit():
                num_value = int(char_text)
                if 1 <= num_value <= 3500:
                    return (num_value, 'Single', False)
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
                if 1 <= num_value <= 3500:
                    orientation = 'Vertical' if is_vertical else 'Horizontal'
                    return (num_value, orientation, False)
            except:
                pass

        return None

    except Exception:
        return None

def extract_all_valid_numbers_from_page(page):
    """Trích xuất TẤT CẢ số hợp lệ"""
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
                    num_value = int(group[0]['text'])
                    fontname = group[0].get('fontname', 'Unknown')
                    font_weight = get_font_weight(group[0])
                    x_pos = group[0]['x0']
                    y_pos = group[0]['top']

                    if 0 < num_value <= 3500:
                        metrics = calculate_advanced_metrics_with_rotation(group, num_value, x_pos, y_pos, 'Single')

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

def create_character_groups_for_all_numbers_with_decimals(digit_and_dot_chars):
    """Tạo các nhóm ký tự cho TẤT CẢ số bao gồm số thập phân"""
    char_groups = []
    used_chars = set()

    sorted_chars = sorted(digit_and_dot_chars, key=lambda c: (c['top'], c['x0']))

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

def should_group_characters_for_all_numbers_with_decimals(base_char, other_char, current_group):
    """Xác định xem 2 ký tự có nên được nhóm lại không"""
    try:
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

def process_character_group_for_all_numbers_with_decimals(group):
    """Xử lý nhóm ký tự cho TẤT CẢ số bao gồm số thập phân"""
    try:
        if len(group) < 2:
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

def create_dimension_summary_with_score_priority(df, df_all_numbers):
    """Tạo bảng tóm tắt với logic GRAIN_Orientation mới"""
    if len(df) == 0:
        return pd.DataFrame(columns=["Drawing#", "Length (mm)", "Width (mm)", "Height (mm)", "Laminate", "FOIL", "EDGEBAND", "Profile"])

    if 'SCORE' in df_all_numbers.columns and len(df_all_numbers) > 0:
        group_scores = df_all_numbers.groupby('Group')['SCORE'].first().sort_values(ascending=False)

        if len(group_scores) > 0:
            highest_score_group = group_scores.index[0]
            high_score_group_data = df_all_numbers[df_all_numbers['Group'] == highest_score_group]
            high_score_numbers = high_score_group_data['Valid Number'].tolist()

            grain_orientation = ""
            if 'GRAIN_Orientation' in high_score_group_data.columns:
                grain_orientations = high_score_group_data['GRAIN_Orientation'].tolist()
                if grain_orientations:
                    valid_grains = [g for g in grain_orientations if g]
                    if valid_grains:
                        grain_counts = Counter(valid_grains)
                        grain_orientation = grain_counts.most_common(1)[0][0]

            unique_numbers = sorted(list(set(high_score_numbers)), reverse=True)
        else:
            all_numbers = df['Number_Int'].tolist()
            unique_numbers = sorted(list(set(all_numbers)), reverse=True)
            grain_orientation = ""
    else:
        all_numbers = df['Number_Int'].tolist()
        unique_numbers = sorted(list(set(all_numbers)), reverse=True)
        grain_orientation = ""

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

    filename = df.iloc[0]['File']
    drawing_name = filename.replace('.pdf', '') if filename.endswith('.pdf') else filename

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

# =============================================================================
# STREAMLIT APP
# =============================================================================

def main():
    st.set_page_config(page_title="PDF Processor", layout="wide")
    
    # CSS để ẩn các thông tin không cần thiết
    st.markdown("""
        <style>
        .stDeployButton {display:none;}
        footer {visibility: hidden;}
        .stDecoration {display:none;}
        header {visibility: hidden;}
        .main .block-container {
            padding-top: 1rem;
        }
        </style>
    """, unsafe_allow_html=True)

    # Giao diện tải file
    uploaded_files = st.file_uploader(
        "Chọn file PDF để xử lý",
        type=['pdf'],
        accept_multiple_files=True,
        help="Kéo thả hoặc click để chọn file PDF"
    )

    if uploaded_files:
        # Initialize result arrays
        main_table_results = []
        secondary_table_results = []

        # Progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()

        # XỬ LÝ TỪNG FILE RIÊNG BIỆT
        for file_idx, uploaded_file in enumerate(uploaded_files):
            status_text.text(f'Đang xử lý file {file_idx+1}/{len(uploaded_files)}: {uploaded_file.name}')
            
            try:
                with pdfplumber.open(uploaded_file) as pdf:
                    total_pages = len(pdf.pages)

                    if total_pages == 0:
                        continue

                    # CHỈ XỬ LÝ TRANG ĐẦU TIÊN
                    page = pdf.pages[0]

                    # Trích xuất thông tin profile
                    profile_info = extract_profile_from_page(page)

                    # Trích xuất thông tin FOIL classification và detail
                    foil_classification, foil_detail = extract_foil_classification_with_detail(page)

                    # Trích xuất thông tin EDGEBAND classification và detail
                    edgeband_classification, edgeband_detail = extract_edgeband_classification_with_detail(page)

                    # Trích xuất thông tin LAMINATE classification
                    laminate_classification, laminate_detail = extract_laminate_classification_with_detail(page)

                    # Sử dụng phương pháp trích xuất mới (CHO BẢNG CHÍNH)
                    char_numbers, char_orientations, font_info = extract_numbers_and_decimals_from_chars(page)

                    # Trích xuất TẤT CẢ số hợp lệ (CHO BẢNG PHỤ)
                    all_valid_numbers = extract_all_valid_numbers_from_page(page)

                    # Xử lý kết quả cho BẢNG CHÍNH
                    file_main_results = []
                    for i, number in enumerate(char_numbers):
                        key = f"{number}_{i+1}"
                        orientation = char_orientations.get(key, 'Horizontal')
                        fontname = font_info.get(key, {}).get('fontname', 'Unknown')
                        font_weight = font_info.get(key, {}).get('font_weight', 'Unknown')

                        file_main_results.append({
                            "File": uploaded_file.name,
                            "Number": str(number),
                            "Font Name": fontname,
                            "Font Weight": font_weight,
                            "Orientation": orientation,
                            "Number_Int": number,
                            "Profile": profile_info,
                            "FOIL": foil_classification,
                            "EDGEBAND": edgeband_classification,
                            "Laminate": laminate_classification,
                            "Index": i+1
                        })

                    # Xử lý kết quả cho BẢNG PHỤ (tất cả số hợp lệ)
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
                            "Index": i+1,
                            "Page": page
                        })

                    # XỬ LÝ BẢNG PHỤ CHO FILE NÀY
                    if file_secondary_results:
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

                        # Tìm GRAIN cho group có score cao nhất
                        df_file_secondary['GRAIN_Orientation'] = ""

                        # Tìm group có score cao nhất trong file này
                        group_scores = df_file_secondary.groupby('Group')['SCORE'].first().sort_values(ascending=False)

                        if len(group_scores) > 0:
                            highest_score_group = group_scores.index[0]
                            group_data = df_file_secondary[df_file_secondary['Group'] == highest_score_group]

                            if len(group_data) > 0:
                                # Lấy page object từ record đầu tiên
                                page = group_data['Page'].iloc[0]

                                # Tìm GRAIN cho nhóm
                                found_idx, grain_orientation = search_grain_text_for_group_by_priority(page, group_data)

                                if found_idx is not None and grain_orientation:
                                    df_file_secondary.loc[found_idx, 'GRAIN_Orientation'] = grain_orientation

                        # Dọn dẹp cột Page
                        df_file_secondary = df_file_secondary.drop(columns=['Page'])

                        # Thêm vào kết quả tổng
                        secondary_table_results.extend(df_file_secondary.to_dict('records'))

                    # Thêm kết quả bảng chính vào tổng
                    main_table_results.extend(file_main_results)

            except Exception as e:
                st.error(f"Lỗi xử lý file {uploaded_file.name}: {str(e)}")
                continue

            # Cập nhật progress bar
            progress_bar.progress((file_idx + 1) / len(uploaded_files))

        status_text.text('Hoàn thành!')

        # TẠO DATAFRAMES TỔNG HỢP
        df_all = pd.DataFrame(main_table_results).reset_index(drop=True)
        df_all_numbers = pd.DataFrame(secondary_table_results).reset_index(drop=True)

        # XỬ LÝ VÀ HIỂN THỊ KẾT QUẢ
        if not df_all.empty:
            df_final = df_all.copy()
            df_final = df_final.drop(columns=["Index"])

            # Tạo bảng tóm tắt cho từng file
            summary_results = []
            for file_group in df_final.groupby("File"):
                filename, file_data = file_group

                # Lấy df_all_numbers cho file này
                file_all_numbers = df_all_numbers[df_all_numbers['File'] == filename] if not df_all_numbers.empty else pd.DataFrame()

                summary = create_dimension_summary_with_score_priority(file_data, file_all_numbers)
                summary_results.append(summary)

            # Kết hợp tất cả kết quả
            final_summary = pd.concat(summary_results, ignore_index=True) if summary_results else pd.DataFrame(columns=["Drawing#", "Length (mm)", "Width (mm)", "Height (mm)", "Laminate", "FOIL", "EDGEBAND", "Profile"])

            # HIỂN THỊ KẾT QUẢ - CHỈ BẢNG CHÍNH
            st.dataframe(final_summary, use_container_width=True)

            # Nút export Excel
            if not final_summary.empty:
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    final_summary.to_excel(writer, sheet_name='Main_Results', index=False)
                
                output.seek(0)
                
                st.download_button(
                    label="📁 Export Excel",
                    data=output.getvalue(),
                    file_name="pdf_processing_results.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        else:
            st.write("Không có dữ liệu để hiển thị")

if __name__ == "__main__":
    main()



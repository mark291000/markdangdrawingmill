import streamlit as st
import pdfplumber
import pandas as pd
import re
import numpy as np
from collections import Counter
import math
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import euclidean_distances
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

        # Kiểm tra các từ khóa phổ biến cho độ đậm
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

        # Xác định có phải số dọc không
        is_vertical = (orientation == 'Vertical')

        # ============= TÍNH 3 CHỈ SỐ SAU KHI XOAY =============

        # 1. Font Size (trung bình) - CHỈ TÍNH CHO KÝ TỰ SỐ
        font_sizes = [c.get('size', 0) for c in group if 'size' in c and c.get('text', '').isdigit()]
        if font_sizes:
            metrics['font_size'] = round(sum(font_sizes) / len(font_sizes), 1)
        else:
            metrics['font_size'] = 0.0

        # *** THÊM KIỂM TRA LOẠI BỎ FONT_SIZE = 20.6 ***
        if metrics['font_size'] == 20.6:
            return None

        # 2 & 3. Character Width và Height - CHỈ TÍNH CHO KÝ TỰ SỐ - XOAY NẾU LÀ SỐ DỌC
        char_widths = []
        char_heights = []

        # *** CHỈ LẤY KÝ TỰ SỐ, BỎ QUA DẤU CHẤM ***
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
                # SỐ DỌC: Đổi chỗ width và height để về orientation ngang
                metrics['char_width'] = round(avg_height, 1)   # Width sau xoay = Height gốc
                metrics['char_height'] = round(avg_width, 1)   # Height sau xoay = Width gốc
            else:
                # SỐ NGANG: Giữ nguyên
                metrics['char_width'] = round(avg_width, 1)
                metrics['char_height'] = round(avg_height, 1)
        else:
            metrics['char_width'] = 0.0
            metrics['char_height'] = 0.0

        # ============= CÁC CHỈ SỐ KHÁC (SỬ DỤNG METRICS ĐÃ XOAY) =============

        # 4. Density Score (sử dụng char_width và char_height đã xoay - CHỈ TÍNH KÝ TỰ SỐ)
        if metrics['char_width'] > 0 and metrics['char_height'] > 0:
            total_area = metrics['char_width'] * len(digit_chars) * metrics['char_height']  # Dùng len(digit_chars)
            if total_area > 0:
                metrics['density_score'] = round(len(digit_chars) / total_area * 1000, 2)  # Dùng len(digit_chars)
            else:
                metrics['density_score'] = 0.0
        else:
            metrics['density_score'] = 0.0

        # 5. Distance from Origin (không đổi)
        origin_distance = math.sqrt(x_pos**2 + y_pos**2)
        metrics['distance_from_origin'] = round(origin_distance, 1)

        # 6. Aspect Ratio (sử dụng metrics đã xoay - CHỈ KÝ TỰ SỐ)
        if metrics['char_height'] > 0:
            total_width = metrics['char_width'] * len(digit_chars)  # Dùng len(digit_chars)
            aspect_ratio = total_width / metrics['char_height']
            metrics['aspect_ratio'] = round(aspect_ratio, 2)
        else:
            metrics['aspect_ratio'] = 0.0

        # 7. Character Spacing (tính theo orientation gốc rồi xoay nếu cần - CHỈ KÝ TỰ SỐ)
        if len(digit_chars) > 1:  # Dùng digit_chars thay vì group
            spacings = []

            if is_vertical:
                # Số dọc: Spacing theo Y (vertical)
                sorted_chars = sorted(digit_chars, key=lambda c: c.get('top', 0))  # Dùng digit_chars
                for i in range(len(sorted_chars) - 1):
                    current_char = sorted_chars[i]
                    next_char = sorted_chars[i + 1]
                    if 'bottom' in current_char and 'top' in next_char:
                        spacing = next_char['top'] - current_char['bottom']
                        spacings.append(abs(spacing))
            else:
                # Số ngang: Spacing theo X (horizontal)
                sorted_chars = sorted(digit_chars, key=lambda c: c.get('x0', 0))  # Dùng digit_chars
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

        # 8. Text Angle (chuẩn hóa về 0 độ sau xoay - CHỈ KÝ TỰ SỐ)
        if is_vertical:
            metrics['text_angle'] = 0.0  # Đã xoay về ngang
        else:
            # Tính góc cho số ngang - CHỈ KÝ TỰ SỐ
            if len(digit_chars) > 1:  # Dùng digit_chars
                sorted_chars = sorted(digit_chars, key=lambda c: c.get('x0', 0))  # Dùng digit_chars
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
    """
    Tính SCORE cho nhóm theo các tiêu chí:
    - Group có từ 3 đến 5 number thì +10đ
    - Char_Spacing tất cả number trong group chênh lệch nhau <0.2 thì +10đ
    - Has_HV_Mix = true thì +10đ
    """
    score = 0

    # Tiêu chí 1: Group có từ 3 đến 5 number thì +10đ
    group_size = len(group_data)
    if group_size == 3:
        score += 30
    elif group_size == 5:
       score += 10

    # Tiêu chí 2: Char_Spacing tất cả number trong group chênh lệch nhau <0.2 thì +10đ
    char_spacings = group_data['Char_Spacing'].tolist()
    if len(char_spacings) > 1:
        max_spacing = max(char_spacings)
        min_spacing = min(char_spacings)
        spacing_diff = max_spacing - min_spacing

        if spacing_diff < 0.2:
            score += 10

    # Tiêu chí 3: Has_HV_Mix = true thì +10đ
    has_hv_mix = group_data['Has_HV_Mix'].iloc[0] if len(group_data) > 0 else False
    if has_hv_mix:
        score += 20

    return score

def check_grain_exists_in_page(page):
    """
    *** MỚI: Kiểm tra xem trang có chứa chữ GRAIN/NIARG không ***
    """
    try:
        text = page.extract_text()
        if not text:
            return False

        text_upper = text.upper()
        has_grain = 'GRAIN' in text_upper or 'NIARG' in text_upper

        return has_grain

    except Exception as e:
        return False

def extract_lines_from_pdf(pdf_path):
    """Trích xuất text ra từng dòng từ PDF"""
    lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text()
            if page_text:
                for line_num, line in enumerate(page_text.split("\n"), start=1):
                    lines.append((page_num, line_num, line.strip()))
    return lines

def extract_laminate_classification_with_detail(page):
    """
    *** CẬP NHẬT: Logic mới - Lấy cặp keyword đầu tiên theo thứ tự xuất hiện từ trên xuống ***
    *** CẬP NHẬT THÊM: Nếu chỉ tìm thấy 1 keyword thì để trống ***
    """
    try:
        # Danh sách keyword theo thứ tự ưu tiên
        keywords = [
            "FLEX PAPER/PAPER",
            "GLUEABLE LAM",
            "GLUEABLE LAM/TC BLACK (IF APPLICABLE)",
            "LAM/MASKING (IF APPLICABLE)",
            "RAW",
            "LAM"
        ]

        # Trích text ra từng dòng
        lines = []
        page_text = page.extract_text()
        if page_text:
            for line_num, line in enumerate(page_text.split("\n"), start=1):
                lines.append((line_num, line.strip()))
        else:
            return "", ""

        # Tìm tất cả keyword theo thứ tự xuất hiện trong PDF
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

        # *** CẬP NHẬT: CHỈ TRẢ VỀ KẾT QUẢ NẾU CÓ ÍT NHẤT 2 KEYWORD ***
        if len(all_found) >= 2:
            first_kw = all_found[0]["Keyword"]
            second_kw = all_found[1]["Keyword"]
            result = f"{first_kw}/{second_kw}"
            detail = f"Found: {first_kw} (line {all_found[0]['Line']}), {second_kw} (line {all_found[1]['Line']})"
            return result, detail
        elif len(all_found) == 1:
            return "", ""  # *** ĐỂ TRỐNG NẾU CHỈ CÓ 1 KEYWORD ***
        else:
            return "", ""

    except Exception as e:
        return "", ""

# [Continue with all other functions - I'll provide the essential ones and indicate where others continue]

def find_keyword_positions(text_chars, keyword):
    """Tìm vị trí của từ khóa trong danh sách ký tự - CẬP NHẬT ĐỂ TRẢ VỀ NHIỀU VỊ TRÍ"""
    positions = []

    try:
        # Chuyển keyword thành chữ hoa để so sánh
        keyword_upper = keyword.upper()
        keyword_chars = list(keyword_upper.replace('/', '').replace('(', '').replace(')', '').replace(' ', ''))

        if not keyword_chars:
            return positions

        # Tạo text liên tục từ các ký tự
        char_data = []
        for char in text_chars:
            char_text = char.get('text', '').upper()
            if char_text.strip():
                char_data.append({
                    'text': char_text,
                    'x': char.get('x0', 0),
                    'y': char.get('top', 0),
                    'char_obj': char
                })

        # Tìm kiếm chuỗi con - TÌM TẤT CẢ VỊ TRÍ
        for i in range(len(char_data)):
            # Thử khớp từ vị trí i
            match_chars = []
            keyword_idx = 0

            for j in range(i, len(char_data)):
                if keyword_idx >= len(keyword_chars):
                    break

                char_text = char_data[j]['text']

                # Bỏ qua các ký tự không phải chữ/số
                if not char_text.isalnum():
                    continue

                # Kiểm tra khớp ký tự
                if char_text == keyword_chars[keyword_idx]:
                    match_chars.append(char_data[j])
                    keyword_idx += 1
                else:
                    # Không khớp, thoát khỏi vòng lặp này
                    break

            # Nếu khớp đủ từ khóa
            if keyword_idx >= len(keyword_chars) and match_chars:
                # Tính vị trí trung bình
                avg_x = sum(c['x'] for c in match_chars) / len(match_chars)
                avg_y = sum(c['y'] for c in match_chars) / len(match_chars)

                # Kiểm tra không trùng lặp vị trí (tránh tìm cùng một keyword nhiều lần)
                is_duplicate = False
                for existing_pos in positions:
                    if (abs(existing_pos['x'] - avg_x) < 10 and
                        abs(existing_pos['y'] - avg_y) < 10):
                        is_duplicate = True
                        break

                if not is_duplicate:
                    positions.append({
                        'x': avg_x,
                        'y': avg_y,
                        'chars': match_chars,
                        'keyword': keyword
                    })

        return positions

    except Exception as e:
        return positions

# [Continue with other essential functions...]

def search_grain_text_for_group_by_priority(page, group_data, search_distance=200):
    """
    *** UPDATED: Kiểm tra GRAIN trước, nếu có thì mới tìm theo trục và hình vuông ***
    """
    try:
        # BƯỚC 1: Kiểm tra có GRAIN trong trang không
        if not check_grain_exists_in_page(page):
            return None, ""

        # BƯỚC 2: Nếu có GRAIN, tiến hành tìm kiếm như cũ
        # Sắp xếp group_data theo số từ lớn đến nhỏ
        sorted_group = group_data.sort_values('Valid Number', ascending=False)

        for idx, row in sorted_group.iterrows():
            num_value = row['Valid Number']
            num_x = row['Position_X']
            num_y = row['Position_Y']
            num_orientation = row['Orientation']

            # Thử tìm theo trục trước
            grain_result = search_grain_along_axis(page, num_x, num_y, num_orientation, search_distance)

            if grain_result:
                return idx, grain_result
            else:
                # Nếu không tìm thấy theo trục, tìm trong hình vuông 200px
                grain_result = search_grain_in_square_area(page, num_x, num_y, search_distance)

                if grain_result:
                    return idx, grain_result

        return None, ""

    except Exception as e:
        return None, ""

def search_grain_along_axis(page, num_x, num_y, num_orientation, search_distance=200):
    """
    Tìm GRAIN/NIARG theo trục (vuông góc với orientation của number)
    TRẢ VỀ ORIENTATION: "Horizontal" cho GRAIN, "Vertical" cho NIARG
    """
    try:
        chars = page.chars
        if not chars:
            return ""

        # Xác định hướng trục GRAIN (vuông góc với number)
        if num_orientation == 'Horizontal':
            # Number ngang → trục GRAIN dọc (tìm theo Y)
            search_axis = 'vertical'
        elif num_orientation == 'Vertical':
            # Number dọc → trục GRAIN ngang (tìm theo X)
            search_axis = 'horizontal'
        else:
            # Single → thử cả 2 trục
            search_axis = 'both'

        # Lấy tất cả ký tự text từ page
        text_chars = [c for c in chars if c.get('text', '').isalpha()]

        # Tìm ký tự trong vùng trục GRAIN
        candidate_chars = []

        for char in text_chars:
            char_x = char.get('x0', 0)
            char_y = char.get('top', 0)
            char_text = char.get('text', '').upper()

            # Kiểm tra ký tự có nằm trên trục không
            on_axis = False

            if search_axis == 'horizontal':
                # Trục ngang: cùng Y, khác X
                if (abs(char_y - num_y) <= 20 and  # Cùng hàng Y (±20px)
                    abs(char_x - num_x) <= search_distance):  # Trong phạm vi tìm kiếm X
                    on_axis = True

            elif search_axis == 'vertical':
                # Trục dọc: cùng X, khác Y
                if (abs(char_x - num_x) <= 20 and  # Cùng cột X (±20px)
                    abs(char_y - num_y) <= search_distance):  # Trong phạm vi tìm kiếm Y
                    on_axis = True

            elif search_axis == 'both':
                # Thử cả 2 trục cho Single
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

        # Sắp xếp theo khoảng cách gần nhất
        candidate_chars.sort(key=lambda c: c['distance'])

        # Thử ghép thành chữ GRAIN hoặc NIARG
        if len(candidate_chars) >= 5:
            grain_sequence_info = find_grain_sequence_with_direction(candidate_chars)

            if grain_sequence_info:
                sequence_type = grain_sequence_info['type']  # 'GRAIN' hoặc 'NIARG'
                text_direction = grain_sequence_info['direction']  # 'Horizontal' hoặc 'Vertical'

                # *** CHUYỂN ĐỔI THEO QUY TẮC MỚI ***
                if sequence_type == "GRAIN":
                    result = "Horizontal"  # GRAIN → Horizontal
                elif sequence_type == "NIARG":
                    result = "Vertical"    # NIARG → Vertical
                else:
                    result = "Horizontal"  # Default

                return result

        return ""

    except Exception as e:
        return ""

def search_grain_in_square_area(page, num_x, num_y, search_distance=200):
    """
    Tìm GRAIN/NIARG trong phạm vi hình vuông quanh number
    TRẢ VỀ ORIENTATION: "Horizontal" cho GRAIN, "Vertical" cho NIARG
    """
    try:
        chars = page.chars
        if not chars:
            return ""

        # Lấy tất cả ký tự text từ page
        text_chars = [c for c in chars if c.get('text', '').isalpha()]

        # Tìm ký tự trong hình vuông
        candidate_chars = []

        for char in text_chars:
            char_x = char.get('x0', 0)
            char_y = char.get('top', 0)
            char_text = char.get('text', '').upper()

            # Kiểm tra ký tự có nằm trong hình vuông không
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

        # Sắp xếp theo khoảng cách gần nhất
        candidate_chars.sort(key=lambda c: c['distance'])

        # Thử ghép thành chữ GRAIN hoặc NIARG
        if len(candidate_chars) >= 5:
            grain_sequence_info = find_grain_sequence_with_direction(candidate_chars)

            if grain_sequence_info:
                sequence_type = grain_sequence_info['type']  # 'GRAIN' hoặc 'NIARG'
                text_direction = grain_sequence_info['direction']  # 'Horizontal' hoặc 'Vertical'

                # *** CHUYỂN ĐỔI THEO QUY TẮC MỚI ***
                if sequence_type == "GRAIN":
                    result = "Horizontal"  # GRAIN → Horizontal
                elif sequence_type == "NIARG":
                    result = "Vertical"    # NIARG → Vertical
                else:
                    result = "Horizontal"  # Default

                return result

        return ""

    except Exception as e:
        return ""

def find_grain_sequence_with_direction(candidate_chars):
    """
    *** MỚI: Tìm chuỗi GRAIN/NIARG và xác định hướng dựa trên layout của text ***
    """
    try:
        # Nhóm ký tự theo loại
        char_groups = {}
        for char_info in candidate_chars:
            char_type = char_info['char']
            if char_type not in char_groups:
                char_groups[char_type] = []
            char_groups[char_type].append(char_info)

        # Kiểm tra có đủ từng loại ký tự không
        required_chars = ['G', 'R', 'A', 'I', 'N']
        for required_char in required_chars:
            if required_char not in char_groups or len(char_groups[required_char]) == 0:
                return None

        # Chọn 1 ký tự đại diện từ mỗi loại (gần nhất với trung điểm)
        representative_chars = {}
        for char_type in required_chars:
            # Chọn ký tự gần trung điểm nhất trong loại này
            closest_char = min(char_groups[char_type], key=lambda c: c['distance'])
            representative_chars[char_type] = closest_char

        # *** PHÂN TÍCH LAYOUT CỦA TEXT GRAIN ***
        char_positions = [(char_type, char_info['x'], char_info['y'])
                         for char_type, char_info in representative_chars.items()]

        # Tính span theo X và Y
        x_positions = [pos[1] for pos in char_positions]
        y_positions = [pos[2] for pos in char_positions]

        x_span = max(x_positions) - min(x_positions)
        y_span = max(y_positions) - min(y_positions)

        # Xác định hướng của text GRAIN
        if x_span > y_span * 1.5:
            text_direction = "Horizontal"  # Text nằm ngang
        elif y_span > x_span * 1.5:
            text_direction = "Vertical"    # Text nằm dọc
        else:
            # Không rõ ràng → mặc định Horizontal
            text_direction = "Horizontal"

        # *** XÁC ĐỊNH THỨ TỰ GRAIN VS NIARG ***
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
        # Sắp xếp ký tự theo hướng của text
        if text_direction == "Horizontal":
            # Text ngang → sắp xếp theo X (trái sang phải)
            sorted_items = sorted(representative_chars.items(), key=lambda x: x[1]['x'])
        else:
            # Text dọc → sắp xếp theo Y (trên xuống dưới)
            sorted_items = sorted(representative_chars.items(), key=lambda x: x[1]['y'])

        # Lấy thứ tự các ký tự
        sequence = "".join([char_type for char_type, char_info in sorted_items])

        # Kiểm tra thứ tự
        if "GRAIN" in sequence:
            return "GRAIN"
        elif "NIARG" in sequence:
            return "NIARG"
        else:
            # Tính điểm tương đồng
            grain_score = calculate_sequence_similarity(sequence, "GRAIN")
            niarg_score = calculate_sequence_similarity(sequence, "NIARG")

            if grain_score >= niarg_score:
                return "GRAIN"
            else:
                return "NIARG"

    except Exception as e:
        return "GRAIN"  # Default

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

# [Continue with grouping and other functions...]

def expand_small_groups(df):
    """
    Mở rộng các nhóm chỉ có 2 số bằng cách tìm số có:
    - Font_Size = Char_Width
    - Char_Width = Char_Width (cùng với nhóm)
    - Char_Height chênh lệch ≤ 0.2
    - CHO PHÉP Single orientation từ các nhóm khác tham gia
    """
    try:
        # Tìm các nhóm có đúng 2 số
        group_counts = df['Group'].value_counts()
        groups_with_2_numbers = group_counts[group_counts == 2].index.tolist()

        if not groups_with_2_numbers:
            return df

        for group_name in groups_with_2_numbers:
            # Lấy thông tin nhóm hiện tại
            group_data = df[df['Group'] == group_name]
            if len(group_data) != 2:
                continue

            # Lấy Char_Width chung của nhóm
            group_char_widths = group_data['Char_Width'].unique()
            if len(group_char_widths) != 1:
                continue

            target_char_width = group_char_widths[0]
            group_char_heights = group_data['Char_Height'].tolist()
            group_font_names = group_data['Font Name'].unique()
            group_orientations = set(group_data['Orientation'].tolist())

            # Tìm các số có thể bổ sung - BAO GỒM CẢ UNGROUPED VÀ CÁC NHÓM KHÁC
            candidate_data = df[df['Group'] != group_name]  # Tất cả số KHÔNG thuộc nhóm hiện tại

            candidates = []
            for idx, row in candidate_data.iterrows():
                candidate_font_size = row['Font_Size']
                candidate_char_width = row['Char_Width']
                candidate_char_height = row['Char_Height']
                candidate_font_name = row['Font Name']
                candidate_orientation = row['Orientation']
                candidate_current_group = row['Group']

                # *** THÊM KIỂM TRA LOẠI BỎ FONT_SIZE = 20.6 ***
                if candidate_font_size == 20.6:
                    continue

                # Kiểm tra điều kiện cơ bản
                condition_1 = (candidate_font_size == candidate_char_width)  # Font_Size = Char_Width
                condition_2 = (candidate_char_width == target_char_width)    # Char_Width = Char_Width nhóm
                condition_3 = any(abs(candidate_char_height - gh) <= 0.2 for gh in group_char_heights)  # Char_Height chênh lệch ≤ 0.2
                condition_4 = (candidate_font_name in group_font_names)      # Cùng font name

                # *** MỚI: Điều kiện cho phép Single orientation ***
                condition_5 = True  # Mặc định cho phép

                # Nếu ứng viên là Single thì luôn được phép
                if candidate_orientation == 'Single':
                    condition_5 = True

                # Nếu ứng viên không phải Single, kiểm tra logic H/V Mix
                elif candidate_orientation in ['Horizontal', 'Vertical']:
                    # Chỉ cho phép nếu tạo thành pattern H/V Mix hợp lệ
                    new_orientations = group_orientations | {candidate_orientation}
                    if len(new_orientations) > len(group_orientations):  # Thêm orientation mới
                        condition_5 = True
                    else:
                        condition_5 = False  # Trùng orientation đã có

                if condition_1 and condition_2 and condition_3 and condition_4 and condition_5:
                    candidates.append({
                        'index': idx,
                        'number': row['Valid Number'],
                        'font_size': candidate_font_size,
                        'char_width': candidate_char_width,
                        'char_height': candidate_char_height,
                        'font_name': candidate_font_name,
                        'orientation': candidate_orientation,
                        'current_group': candidate_current_group
                    })

            # Thêm các ứng viên vào nhóm
            if candidates:
                groups_to_check_empty = set()  # Theo dõi các nhóm có thể trở thành rỗng

                for candidate in candidates:
                    old_group = candidate['current_group']
                    if old_group != 'UNGROUPED':
                        groups_to_check_empty.add(old_group)

                    # Chuyển số sang nhóm mới
                    df.loc[candidate['index'], 'Group'] = group_name
                    df.loc[candidate['index'], 'Has_HV_Mix'] = True  # Đánh dấu có mix

                # Cập nhật Has_HV_Mix cho toàn bộ nhóm
                df.loc[df['Group'] == group_name, 'Has_HV_Mix'] = True

                # Kiểm tra và xử lý các nhóm có thể trở thành rỗng hoặc chỉ còn 1 số
                for old_group in groups_to_check_empty:
                    remaining_count = len(df[df['Group'] == old_group])
                    if remaining_count == 0:
                        pass  # Nhóm đã trống
                    elif remaining_count == 1:
                        # Đặt lại số cuối cùng thành UNGROUPED
                        last_number_idx = df[df['Group'] == old_group].index[0]
                        df.loc[last_number_idx, 'Group'] = 'UNGROUPED'
                        df.loc[last_number_idx, 'Has_HV_Mix'] = False

        return df

    except Exception as e:
        return df

def expand_group_to_minimum_3_members(df):
    """
    *** MỚI: Mở rộng group có 2 thành viên để đảm bảo có ít nhất 3 thành viên ***
    Điều kiện: cùng Font Name, cùng Char_Width và Char_Height chênh lệch ≤ 0.2
    """
    try:
        # Tìm các nhóm có đúng 2 số
        group_counts = df['Group'].value_counts()
        groups_with_2_numbers = [g for g in group_counts.index if group_counts[g] == 2 and g not in ['UNGROUPED', 'INSUFFICIENT_DATA', 'ERROR']]

        if not groups_with_2_numbers:
            return df

        for group_name in groups_with_2_numbers:
            # Lấy thông tin nhóm hiện tại
            group_data = df[df['Group'] == group_name]
            if len(group_data) != 2:
                continue

            # Lấy Font Name và Char_Width chung của nhóm
            group_font_names = group_data['Font Name'].unique()
            group_char_widths = group_data['Char_Width'].unique()
            group_char_heights = group_data['Char_Height'].tolist()

            if len(group_font_names) != 1 or len(group_char_widths) != 1:
                continue

            target_font_name = group_font_names[0]
            target_char_width = group_char_widths[0]

            # Tìm các số có thể bổ sung từ UNGROUPED hoặc các nhóm khác
            candidate_data = df[df['Group'] != group_name]

            candidates = []
            for idx, row in candidate_data.iterrows():
                candidate_font_name = row['Font Name']
                candidate_char_width = row['Char_Width']
                candidate_char_height = row['Char_Height']
                candidate_font_size = row['Font_Size']
                candidate_current_group = row['Group']

                # *** THÊM KIỂM TRA LOẠI BỎ FONT_SIZE = 20.6 ***
                if candidate_font_size == 20.6:
                    continue

                # Kiểm tra điều kiện: cùng Font Name, cùng Char_Width, Char_Height chênh lệch ≤ 0.2
                condition_1 = (candidate_font_name == target_font_name)
                condition_2 = (candidate_char_width == target_char_width)
                condition_3 = any(abs(candidate_char_height - gh) <= 0.2 for gh in group_char_heights)

                if condition_1 and condition_2 and condition_3:
                    candidates.append({
                        'index': idx,
                        'number': row['Valid Number'],
                        'font_name': candidate_font_name,
                        'char_width': candidate_char_width,
                        'char_height': candidate_char_height,
                        'orientation': row['Orientation'],
                        'current_group': candidate_current_group
                    })

            # Thêm ít nhất 1 ứng viên để đạt tối thiểu 3 thành viên
            if candidates:
                # Chọn ứng viên đầu tiên
                selected_candidate = candidates[0]
                old_group = selected_candidate['current_group']

                # Chuyển số sang nhóm mới
                df.loc[selected_candidate['index'], 'Group'] = group_name

                # Xử lý nhóm cũ nếu cần
                if old_group != 'UNGROUPED':
                    remaining_count = len(df[df['Group'] == old_group])
                    if remaining_count == 1:
                        # Đặt lại số cuối cùng thành UNGROUPED
                        last_number_idx = df[df['Group'] == old_group].index[0]
                        df.loc[last_number_idx, 'Group'] = 'UNGROUPED'
                        df.loc[last_number_idx, 'Has_HV_Mix'] = False

        return df

    except Exception as e:
        return df

def check_uniform_metrics_for_has_hv_mix(group_data):
    """
    *** MỚI: Kiểm tra xem tất cả số trong group có cùng Font_Size, Char_Width, Char_Height không ***
    Nếu có thì trả về True (uniform), nếu không thì trả về False
    """
    try:
        if len(group_data) <= 1:
            return True  # Chỉ có 1 số hoặc ít hơn thì coi như uniform

        # Lấy giá trị các metrics từ nhóm
        font_sizes = group_data['Font_Size'].unique()
        char_widths = group_data['Char_Width'].unique()
        char_heights = group_data['Char_Height'].unique()

        # Kiểm tra xem tất cả có cùng giá trị không
        uniform_font_size = len(font_sizes) == 1
        uniform_char_width = len(char_widths) == 1
        uniform_char_height = len(char_heights) == 1

        is_uniform = uniform_font_size and uniform_char_width and uniform_char_height

        return is_uniform

    except Exception as e:
        return False

def group_numbers_by_font_characteristics(df):
    """
    Phân nhóm số theo đặc tính font - CẬP NHẬT LOGIC CHO PHÉP Single orientation nhóm với H/V
    *** CẬP NHẬT: Kiểm tra uniform metrics để đặt Has_HV_Mix = False ***
    """
    try:
        if len(df) < 1:
            df['Group'] = 'INSUFFICIENT_DATA'
            df['Has_HV_Mix'] = False
            return df

        # Khởi tạo cột Group và Has_HV_Mix
        df['Group'] = 'UNGROUPED'
        df['Has_HV_Mix'] = False
        group_counter = 1

        # BƯỚC 1: Tạo các nhóm ban đầu (logic cũ)
        for i, row in df.iterrows():
            if df.loc[i, 'Group'] != 'UNGROUPED':
                continue  # Đã được phân nhóm

            current_font_size = row['Font_Size']
            current_char_width = row['Char_Width']
            current_char_height = row['Char_Height']
            current_orientation = row['Orientation']
            current_font_name = row['Font Name']

            # *** THÊM KIỂM TRA LOẠI BỎ FONT_SIZE = 20.6 ***
            if current_font_size == 20.6:
                continue

            # Tìm tất cả số có cùng đặc tính
            group_indices = [i]  # Bắt đầu với chính nó

            for j, other_row in df.iterrows():
                if i == j or df.loc[j, 'Group'] != 'UNGROUPED':
                    continue

                other_font_size = other_row['Font_Size']
                other_char_width = other_row['Char_Width']
                other_char_height = other_row['Char_Height']
                other_orientation = other_row['Orientation']
                other_font_name = other_row['Font Name']

                # *** THÊM KIỂM TRA LOẠI BỎ FONT_SIZE = 20.6 ***
                if other_font_size == 20.6:
                    continue

                # Kiểm tra điều kiện nhóm
                is_same_group = False

                # ĐIỀU KIỆN 1: Hoàn toàn giống nhau
                if (current_font_size == other_font_size and
                    current_char_width == other_char_width and
                    current_char_height == other_char_height and
                    current_font_name == other_font_name):
                    is_same_group = True

                # ĐIỀU KIỆN 2: Chênh lệch Char_Height ≤ 0.2 + cùng các đặc tính khác
                elif (current_font_name == other_font_name and
                      current_char_width == other_char_width and
                      current_font_size == other_font_size and
                      abs(current_char_height - other_char_height) <= 0.2):
                    is_same_group = True

                # ĐIỀU KIỆN 3: Single orientation với H/V có cùng đặc tính font
                elif (current_font_name == other_font_name and
                      current_char_width == other_char_width and
                      current_font_size == other_font_size and
                      abs(current_char_height - other_char_height) <= 0.2):

                    # Kiểm tra có Single với Horizontal/Vertical không
                    orientations = {current_orientation, other_orientation}
                    if 'Single' in orientations and ('Horizontal' in orientations or 'Vertical' in orientations):
                        is_same_group = True

                # ĐIỀU KIỆN 4: Trường hợp đặc biệt Horizontal/Vertical mix với Char_Height chênh lệch ≤ 0.2
                elif (current_font_name == other_font_name and
                      current_char_width == other_char_width and
                      abs(current_char_height - other_char_height) <= 0.2):

                    # Kiểm tra pattern Horizontal/Vertical (không có Single)
                    if ((current_orientation == 'Horizontal' and other_orientation == 'Vertical') or
                        (current_orientation == 'Vertical' and other_orientation == 'Horizontal')):

                        # LOGIC: Số Vertical phải có Font_Size = Char_Width
                        horizontal_row = row if current_orientation == 'Horizontal' else other_row
                        vertical_row = other_row if current_orientation == 'Horizontal' else row

                        # Kiểm tra: Vertical font_size phải = char_width
                        if vertical_row['Font_Size'] == vertical_row['Char_Width']:
                            is_same_group = True

                if is_same_group:
                    group_indices.append(j)

            # Gán group cho tất cả số trong nhóm
            if len(group_indices) >= 1:
                group_name = f"GROUP_{group_counter}"
                for idx in group_indices:
                    df.loc[idx, 'Group'] = group_name

                if len(group_indices) > 1:
                    numbers_in_group = [df.loc[idx, 'Valid Number'] for idx in group_indices]
                    orientations_in_group = [df.loc[idx, 'Orientation'] for idx in group_indices]
                    font_sizes_in_group = [df.loc[idx, 'Font_Size'] for idx in group_indices]
                    char_heights_in_group = [df.loc[idx, 'Char_Height'] for idx in group_indices]

                    # *** CẬP NHẬT: KIỂM TRA UNIFORM METRICS TRƯỚC KHI ĐẶT HAS_HV_MIX ***
                    group_data = df[df['Group'] == group_name]
                    is_uniform = check_uniform_metrics_for_has_hv_mix(group_data)

                    if is_uniform:
                        # Tất cả metrics giống nhau → Has_HV_Mix = False
                        for idx in group_indices:
                            df.loc[idx, 'Has_HV_Mix'] = False
                    else:
                        # KIỂM TRA CÓ ORIENTATION MIX KHÔNG (bao gồm cả Single)
                        unique_orientations = set(orientations_in_group)
                        if len(unique_orientations) > 1 and ('Horizontal' in unique_orientations or 'Vertical' in unique_orientations or 'Single' in unique_orientations):
                            # Đánh dấu nhóm này có mix
                            for idx in group_indices:
                                df.loc[idx, 'Has_HV_Mix'] = True

                group_counter += 1

        # BƯỚC 2: *** MỞ RỘNG CÁC NHÓM CÓ 2 SỐ ***
        df = expand_small_groups(df)

        # BƯỚC 2.5: *** MỞ RỘNG ĐẶC BIỆT ĐỂ ĐẢM BẢO ÍT NHẤT 3 THÀNH VIÊN ***
        df = expand_group_to_minimum_3_members(df)

        # BƯỚC 3: *** KIỂM TRA LẠI UNIFORM METRICS SAU KHI MỞ RỘNG ***
        for group_name in df['Group'].unique():
            if group_name not in ['UNGROUPED', 'INSUFFICIENT_DATA', 'ERROR']:
                group_data = df[df['Group'] == group_name]
                if len(group_data) > 1:
                    is_uniform = check_uniform_metrics_for_has_hv_mix(group_data)

                    if is_uniform:
                        # Đặt Has_HV_Mix = False cho tất cả số trong nhóm
                        df.loc[df['Group'] == group_name, 'Has_HV_Mix'] = False

        return df

    except Exception as e:
        df['Group'] = 'ERROR'
        df['Has_HV_Mix'] = False
        return df

def extract_foil_classification_with_detail(page):
    """Đếm FOIL/LIOF từ text đơn giản"""
    try:
        # Lấy toàn bộ text từ trang
        text = page.extract_text()
        if not text:
            return "", ""

        # Chuyển về chữ hoa để tìm kiếm
        text_upper = text.upper()

        # Đếm số lần xuất hiện của FOIL và LIOF
        foil_count = text_upper.count('FOIL')
        liof_count = text_upper.count('LIOF')

        # Tạo detail string
        detail_parts = []
        if foil_count > 0:
            detail_parts.append(f"{foil_count} FOIL")
        if liof_count > 0:
            detail_parts.append(f"{liof_count} LIOF")

        detail = ", ".join(detail_parts) if detail_parts else ""

        # Áp dụng quy tắc: FOIL = L, LIOF = S, tối đa 2L2S
        num_long = min(foil_count, 2)  # FOIL = L, tối đa 2
        num_short = min(liof_count, 2)  # LIOF = S, tối đa 2

        # Tạo classification string
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
        # Lấy toàn bộ text từ trang
        text = page.extract_text()
        if not text:
            return "", ""

        # Chuyển về chữ hoa để tìm kiếm
        text_upper = text.upper()

        # Đếm số lần xuất hiện của EDGEBAND và DNABEGDE
        edgeband_count = text_upper.count('EDGEBAND')
        dnabegde_count = text_upper.count('DNABEGDE')

        # Tạo detail string
        detail_parts = []
        if edgeband_count > 0:
            detail_parts.append(f"{edgeband_count} EDGEBAND")
        if dnabegde_count > 0:
            detail_parts.append(f"{dnabegde_count} DNABEGDE")

        detail = ", ".join(detail_parts) if detail_parts else ""

        # Áp dụng quy tắc: EDGEBAND = L, DNABEGDE = S, tối đa 2L2S
        num_long = min(edgeband_count, 2)  # EDGEBAND = L, tối đa 2
        num_short = min(dnabegde_count, 2)  # DNABEGDE = S, tối đa 2

        # Tạo classification string
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
        # Lấy toàn bộ text từ trang
        text = page.extract_text()
        if not text:
            return ""

        # Tìm pattern PROFILE: theo sau bởi mã profile
        profile_pattern = r"PROFILE:\s*([A-Z0-9\-]+)"
        match = re.search(profile_pattern, text, re.IGNORECASE)

        if match:
            return match.group(1).strip()

        # Nếu không tìm thấy pattern chính xác, thử tìm các pattern khác
        # Tìm các dòng chứa từ "profile" và lấy mã sau đó
        lines = text.split('\n')
        for line in lines:
            if 'profile' in line.lower():
                # Tìm pattern có dạng chữ-số-chữ (ví dụ: 0109P-A)
                profile_match = re.search(r'([A-Z0-9]+[A-Z]-[A-Z0-9]+)', line, re.IGNORECASE)
                if profile_match:
                    return profile_match.group(1).strip()

        return ""
    except Exception as e:
        return ""

def is_valid_font(fontname):
    """Kiểm tra font name có hợp lệ không - CHẤP NHẬN CIDFont+F2, CIDFont+F3, F2, F3"""
    valid_fonts = ['CIDFont+F3', 'CIDFont+F2', 'F3', 'F2']
    return fontname in valid_fonts or any(fontname.endswith(f) for f in valid_fonts)

def get_font_priority(fontname):
    """Trả về độ ưu tiên của font - SỐ CÀNG CAO CÀNG ƯU TIÊN"""
    if 'CIDFont+F3' in fontname or fontname == 'F3':
        return 4  # Ưu tiên cao nhất
    elif 'CIDFont+F2' in fontname or fontname == 'F2':
        return 3
    else:
        return 0  # Không hợp lệ

def determine_preferred_font_with_frequency_3(all_fonts, digit_chars):
    """Xác định font ưu tiên - ƯU TIÊN F2/F3, FALLBACK CHO FONT CÓ FREQUENCY = 3"""
    if not all_fonts:
        return None

    # BƯỚC 1: Kiểm tra có font F2/F3 không
    font_priorities = [(font, get_font_priority(font)) for font in all_fonts]
    valid_font_priorities = [(font, priority) for font, priority in font_priorities if priority > 0]

    # Nếu có font F2/F3 hợp lệ
    if valid_font_priorities:
        # Đếm số ký tự của mỗi font F
        font_char_counts = {}
        for char in digit_chars:
            fontname = char.get('fontname', 'Unknown')
            # *** THÊM KIỂM TRA LOẠI BỎ FONT_SIZE = 20.6 ***
            if char.get('size', 0) == 20.6:
                continue
            if fontname in [fp[0] for fp in valid_font_priorities]:
                if fontname not in font_char_counts:
                    font_char_counts[fontname] = []
                font_char_counts[fontname].append(char)

        total_valid_chars = sum(len(chars) for chars in font_char_counts.values())

        # Nếu có từ 3 kết quả trở lên và có cả F2 và F3, ưu tiên theo Position
        if total_valid_chars >= 3 and len(font_char_counts) >= 2:
            font_avg_positions = {}
            for fontname, chars in font_char_counts.items():
                avg_x = sum(c.get('x0', 0) for c in chars) / len(chars)
                avg_y = sum(c.get('top', 0) for c in chars) / len(chars)
                font_avg_positions[fontname] = (avg_x, avg_y)

            # Sắp xếp theo Position_Y giảm dần, sau đó Position_X giảm dần
            sorted_fonts = sorted(font_avg_positions.items(),
                                key=lambda x: (x[1][1], x[1][0]), reverse=True)

            selected_font = sorted_fonts[0][0]
            return selected_font

        else:
            # Chọn theo priority như cũ
            valid_font_priorities.sort(key=lambda x: x[1], reverse=True)
            selected_font = valid_font_priorities[0][0]
            return selected_font

    else:
        # BƯỚC 2: FALLBACK - TÌM FONT CÓ FREQUENCY = 3
        # Đếm số lần xuất hiện của mỗi font - LOẠI BỎ FONT_SIZE = 20.6
        font_frequencies = {}
        for char in digit_chars:
            # *** THÊM KIỂM TRA LOẠI BỎ FONT_SIZE = 20.6 ***
            if char.get('size', 0) == 20.6:
                continue
            fontname = char.get('fontname', 'Unknown')
            if fontname not in font_frequencies:
                font_frequencies[fontname] = 0
            font_frequencies[fontname] += 1

        # Tìm font có frequency chính xác = 3
        fonts_with_freq_3 = [font for font, freq in font_frequencies.items() if freq == 3]

        if fonts_with_freq_3:
            if len(fonts_with_freq_3) == 1:
                # Chỉ có 1 font có frequency = 3
                selected_font = fonts_with_freq_3[0]
                return selected_font
            else:
                # Nhiều font có frequency = 3 -> chọn theo position trung bình cao nhất
                font_avg_positions = {}
                for fontname in fonts_with_freq_3:
                    chars_of_font = [c for c in digit_chars if c.get('fontname', 'Unknown') == fontname and c.get('size', 0) != 20.6]
                    if chars_of_font:
                        avg_x = sum(c.get('x0', 0) for c in chars_of_font) / len(chars_of_font)
                        avg_y = sum(c.get('top', 0) for c in chars_of_font) / len(chars_of_font)
                        font_avg_positions[fontname] = (avg_x, avg_y)

                if font_avg_positions:
                    # Chọn font có position cao nhất
                    sorted_fonts = sorted(font_avg_positions.items(),
                                        key=lambda x: (x[1][1], x[1][0]), reverse=True)
                    selected_font = sorted_fonts[0][0]
                    return selected_font

        # BƯỚC 3: Nếu không có font frequency = 3, tìm font có nhiều ký tự nhất
        # Tìm font có ít nhất 3 ký tự
        valid_fallback_fonts = {font: freq for font, freq in font_frequencies.items() if freq >= 3}

        if valid_fallback_fonts:
            # Chọn font có nhiều ký tự nhất
            selected_font = max(valid_fallback_fonts.items(), key=lambda x: x[1])[0]
            return selected_font
        else:
            return None

# [Continue with remaining extraction functions...]

def extract_numbers_and_decimals_from_chars(page):
    """METHOD: Trích xuất số và số thập phân - CẬP NHẬT LOGIC FONT FREQUENCY"""
    numbers = []
    orientations = {}
    font_info = {}

    try:
        chars = page.chars
        # Lấy cả số và dấu chấm
        digit_and_dot_chars = [c for c in chars if c['text'].isdigit() or c['text'] == '.']

        if not digit_and_dot_chars:
            return numbers, orientations, font_info

        # Lấy tất cả font có trong page và xác định font ưu tiên
        all_fonts = list(set([c.get('fontname', 'Unknown') for c in digit_and_dot_chars]))
        preferred_font = determine_preferred_font_with_frequency_3(all_fonts, digit_and_dot_chars)

        if not preferred_font:
            return numbers, orientations, font_info

        char_groups = create_character_groups_with_decimals(digit_and_dot_chars, preferred_font)
        extracted_numbers = []

        for group in char_groups:
            if len(group) == 1 and group[0]['text'].isdigit():
                try:
                    # *** THÊM KIỂM TRA LOẠI BỎ FONT_SIZE = 20.6 ***
                    if group[0].get('size', 0) == 20.6:
                        continue

                    num_value = int(group[0]['text'])
                    fontname = group[0].get('fontname', 'Unknown')
                    font_weight = get_font_weight(group[0])

                    # CHỈ LẤY SỐ CỦA FONT ƯU TIÊN
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

                    # Chỉ thêm vào nếu là số nguyên hoặc số thập phân hợp lệ
                    if is_decimal:
                        # Số thập phân - thêm vào danh sách với giá trị gốc
                        numbers.append(number)  # Giữ nguyên giá trị thập phân
                    else:
                        # Số nguyên
                        numbers.append(int(number))

                    orientations[f"{number}_{len(numbers)}"] = orientation
                    fonts = [ch.get("fontname", "Unknown") for ch in group]
                    fontname = Counter(fonts).most_common(1)[0][0] if fonts else "Unknown"

                    # Tính độ đậm trung bình cho nhóm
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

    # Lọc chỉ giữ ký tự từ font ưu tiên và loại bỏ Font_Size = 20.6
    valid_chars = [c for c in digit_and_dot_chars if c.get('fontname', 'Unknown') == preferred_font and c.get('size', 0) != 20.6]

    if not valid_chars:
        return char_groups

    sorted_chars = sorted(valid_chars, key=lambda c: (c['top'], c['x0']))

    for i, base_char in enumerate(sorted_chars):
        if id(base_char) in used_chars:
            continue

        current_group = [base_char]
        used_chars.add(id(base_char))

        # Tìm các ký tự gần kề - bao gồm cả dấu chấm
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
    """Xác định xem 2 ký tự có nên được nhóm lại không - BAO GỒM DẤU CHẤM"""
    try:
        # Kiểm tra font - chỉ nhóm các ký tự cùng font ưu tiên
        base_font = base_char.get('fontname', 'Unknown')
        other_font = other_char.get('fontname', 'Unknown')

        if not (base_font == preferred_font and other_font == preferred_font):
            return False

        # *** THÊM KIỂM TRA LOẠI BỎ FONT_SIZE = 20.6 ***
        if base_char.get('size', 0) == 20.6 or other_char.get('size', 0) == 20.6:
            return False

        # Khoảng cách cho phép - hơi lỏng hơn cho dấu chấm
        distance = math.sqrt(
            (base_char['x0'] - other_char['x0'])**2 +
            (base_char['top'] - other_char['top'])**2
        )

        # Khoảng cách tối đa
        if distance > 30:  # Tăng một chút cho dấu chấm
            return False

        # Kiểm tra alignment
        if len(current_group) > 1:
            group_x_span = max(c['x0'] for c in current_group) - min(c['x0'] for c in current_group)
            group_y_span = max(c['top'] for c in current_group) - min(c['top'] for c in current_group)

            is_group_vertical = group_y_span > group_x_span * 1.5

            if is_group_vertical:
                group_x_center = sum(c['x0'] for c in current_group) / len(current_group)
                if abs(other_char['x0'] - group_x_center) > 10:  # Lỏng hơn cho dấu chấm
                    return False
            else:
                group_y_center = sum(c['top'] for c in current_group) / len(current_group)
                if abs(other_char['top'] - group_y_center) > 8:  # Lỏng hơn cho dấu chấm
                    return False

        return True

    except Exception:
        return False

def process_character_group_with_decimals(group, extracted_numbers, preferred_font):
    """Xử lý nhóm ký tự bao gồm số thập phân"""
    try:
        if len(group) < 1:
            return None

        # Kiểm tra font ưu tiên cho cả nhóm
        fonts = [ch.get("fontname", "Unknown") for ch in group]
        if not all(font == preferred_font for font in fonts):
            return None

        # *** THÊM KIỂM TRA LOẠI BỎ FONT_SIZE = 20.6 ***
        if any(ch.get('size', 0) == 20.6 for ch in group):
            return None

        if len(group) == 1:
            # Ký tự đơn lẻ
            char_text = group[0]['text']
            if char_text.isdigit():
                num_value = int(char_text)
                if 1 <= num_value <= 3500:
                    return (num_value, 'Single', False)
            return None

        # Nhóm nhiều ký tự
        x_positions = [c['x0'] for c in group]
        y_positions = [c['top'] for c in group]

        x_span = max(x_positions) - min(x_positions)
        y_span = max(y_positions) - min(y_positions)

        is_vertical = y_span > x_span * 1.5

        if is_vertical:
            # Sắp xếp theo chiều dọc - ĐỌC NGƯỢC LẠI
            vertical_sorted = sorted(group, key=lambda c: c['top'], reverse=True)
            v_text = "".join([c['text'] for c in vertical_sorted])
        else:
            # Sắp xếp theo chiều ngang
            horizontal_sorted = sorted(group, key=lambda c: c['x0'])
            v_text = "".join([c['text'] for c in horizontal_sorted])

        # Xử lý số thập phân
        if '.' in v_text:
            try:
                # Kiểm tra format hợp lệ của số thập phân
                if v_text.count('.') == 1 and not v_text.startswith('.') and not v_text.endswith('.'):
                    num_value = float(v_text)
                    if 0.1 <= num_value <= 3500.0:
                        orientation = 'Vertical' if is_vertical else 'Horizontal'
                        return (num_value, orientation, True)  # True = là số thập phân
            except:
                pass
        else:
            # Số nguyên
            try:
                num_value = int(v_text)
                if 1 <= num_value <= 3500:
                    orientation = 'Vertical' if is_vertical else 'Horizontal'
                    return (num_value, orientation, False)  # False = không phải số thập phân
            except:
                pass

        return None

    except Exception:
        return None

def extract_all_valid_numbers_from_page(page):
    """BẢNG PHỤ: Trích xuất TẤT CẢ số hợp lệ - XOAY TẠI NGUỒN KHI TÍNH METRICS"""
    all_valid_numbers = []

    try:
        chars = page.chars
        digit_and_dot_chars = [c for c in chars if c['text'].isdigit() or c['text'] == '.']

        if not digit_and_dot_chars:
            return all_valid_numbers

        # Nhóm tất cả ký tự digit và dấu chấm thành các số
        char_groups = create_character_groups_for_all_numbers_with_decimals(digit_and_dot_chars)

        for group_idx, group in enumerate(char_groups):
            if len(group) == 1 and group[0]['text'].isdigit():
                # Ký tự đơn lẻ (chỉ số)
                try:
                    # *** THÊM KIỂM TRA LOẠI BỎ FONT_SIZE = 20.6 ***
                    if group[0].get('size', 0) == 20.6:
                        continue

                    num_value = int(group[0]['text'])
                    fontname = group[0].get('fontname', 'Unknown')
                    font_weight = get_font_weight(group[0])
                    x_pos = group[0]['x0']
                    y_pos = group[0]['top']

                    if 0 < num_value <= 3500:
                        # Tính toán 8 chỉ số khác biệt - XOAY TẠI NGUỒN
                        metrics = calculate_advanced_metrics_with_rotation(group, num_value, x_pos, y_pos, 'Single')

                        # *** KIỂM TRA NẾU METRICS TRẢ VỀ NONE (DO FONT_SIZE = 20.6) ***
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
                            # 8 CHỈ SỐ KHÁC BIỆT (ĐÃ XOAY)
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
                # Nhóm nhiều ký tự
                result = process_character_group_for_all_numbers_with_decimals(group)
                if result:
                    number, orientation, is_decimal = result
                    if (is_decimal and 0.1 <= number <= 3500.0) or (not is_decimal and 0 < number <= 3500):
                        fonts = [ch.get("fontname", "Unknown") for ch in group]
                        fontname = Counter(fonts).most_common(1)[0][0] if fonts else "Unknown"

                        # Tính độ đậm trung bình cho nhóm
                        weights = [get_font_weight(ch) for ch in group]
                        weight_counter = Counter(weights)
                        common_weight = weight_counter.most_common(1)[0][0] if weights else "Unknown"

                        avg_x = sum(c['x0'] for c in group) / len(group)
                        avg_y = sum(c['top'] for c in group) / len(group)

                        # Tính toán 8 chỉ số khác biệt - XOAY TẠI NGUỒN
                        metrics = calculate_advanced_metrics_with_rotation(group, number, avg_x, avg_y, orientation)

                        # *** KIỂM TRA NẾU METRICS TRẢ VỀ NONE (DO FONT_SIZE = 20.6) ***
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
                            # 8 CHỈ SỐ KHÁC BIỆT (ĐÃ XOAY)
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

    # Lọc bỏ các ký tự có Font_Size = 20.6
    valid_chars = [c for c in digit_and_dot_chars if c.get('size', 0) != 20.6]

    # Sắp xếp theo vị trí
    sorted_chars = sorted(valid_chars, key=lambda c: (c['top'], c['x0']))

    for i, base_char in enumerate(sorted_chars):
        if id(base_char) in used_chars:
            continue

        current_group = [base_char]
        used_chars.add(id(base_char))

        # Tìm các ký tự gần kề để tạo thành số
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
    """Xác định xem 2 ký tự có nên được nhóm lại không - BAO GỒM DẤU CHẤM - ĐÃ SỬA LỖI"""
    try:
        # *** THÊM KIỂM TRA LOẠI BỎ FONT_SIZE = 20.6 ***
        if base_char.get('size', 0) == 20.6 or other_char.get('size', 0) == 20.6:
            return False

        # Khoảng cách cho phép
        distance = math.sqrt(
            (base_char['x0'] - other_char['x0'])**2 +
            (base_char['top'] - other_char['top'])**2
        )

        # Khoảng cách tối đa
        if distance > 30:
            return False

        # Kiểm tra font - ưu tiên cùng font
        base_font = base_char.get('fontname', 'Unknown')
        other_font = other_char.get('fontname', 'Unknown')
        if base_font != other_font:
            # Cho phép khác font nhưng giảm khoảng cách
            if distance > 20:
                return False

        # Kiểm tra alignment với nhóm hiện tại - ĐÃ SỬA LỖI
        if len(current_group) > 1:
            group_x_span = max(c['x0'] for c in current_group) - min(c['x0'] for c in current_group)
            group_y_span = max(c['top'] for c in current_group) - min(c['top'] for c in current_group)  # SỬA LỖI

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

        # *** THÊM KIỂM TRA LOẠI BỎ FONT_SIZE = 20.6 ***
        if any(ch.get('size', 0) == 20.6 for ch in group):
            return None

        x_positions = [c['x0'] for c in group]
        y_positions = [c['top'] for c in group]

        x_span = max(x_positions) - min(x_positions)
        y_span = max(y_positions) - min(y_positions)

        is_vertical = y_span > x_span * 1.5

        if is_vertical:
            # Sắp xếp theo chiều dọc - ĐỌC NGƯỢC LẠI
            vertical_sorted = sorted(group, key=lambda c: c['top'], reverse=True)
            v_text = "".join([c['text'] for c in vertical_sorted])
        else:
            # Sắp xếp theo chiều ngang
            horizontal_sorted = sorted(group, key=lambda c: c['x0'])
            v_text = "".join([c['text'] for c in horizontal_sorted])

        # Xử lý số thập phân
        if '.' in v_text:
            try:
                # Kiểm tra format hợp lệ của số thập phân
                if v_text.count('.') == 1 and not v_text.startswith('.') and not v_text.endswith('.'):
                    num_value = float(v_text)
                    if 0.1 <= num_value <= 3500.0:
                        orientation = 'Vertical' if is_vertical else 'Horizontal'
                        return (num_value, orientation, True)
            except:
                pass
        else:
            # Số nguyên
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
    """
    *** CẬP NHẬT: Chỉ sử dụng số từ group được chọn, không lấy từ tất cả số ***
    """
    if len(df) == 0:
        return pd.DataFrame(columns=["Drawing#", "Length (mm)", "Width (mm)", "Height (mm)", "Laminate", "FOIL", "EDGEBAND", "Profile"])

    # TÌM NHÓM CÓ SCORE CAO NHẤT VÀ ÍT NHẤT 3 THÀNH VIÊN
    grain_orientation = ""
    selected_numbers = []  # Danh sách số được chọn
    
    if 'SCORE' in df_all_numbers.columns and len(df_all_numbers) > 0:
        # Tính score cho mỗi group và lọc chỉ những group có ít nhất 3 thành viên
        group_sizes = df_all_numbers.groupby('Group').size()
        valid_groups = group_sizes[group_sizes >= 3].index.tolist()

        if valid_groups:
            group_scores = df_all_numbers[df_all_numbers['Group'].isin(valid_groups)].groupby('Group')['SCORE'].first().sort_values(ascending=False)

            if len(group_scores) > 0:
                highest_score_group = group_scores.index[0]
                highest_score = group_scores.iloc[0]

                # *** CHỈ LẤY NUMBERS TỪ NHÓM ĐƯỢC CHỌN ***
                high_score_group_data = df_all_numbers[df_all_numbers['Group'] == highest_score_group]
                selected_numbers = high_score_group_data['Valid Number'].tolist()  # GIỮ NGUYÊN TẤT CẢ, KỂ CẢ TRÙNG LẶP

                # Lấy GRAIN orientation nếu có
                if 'GRAIN_Orientation' in high_score_group_data.columns:
                    grain_orientations = high_score_group_data['GRAIN_Orientation'].tolist()
                    valid_grains = [g for g in grain_orientations if g]
                    if valid_grains:
                        grain_counts = Counter(valid_grains)
                        grain_orientation = grain_counts.most_common(1)[0][0]

            else:
                all_numbers = df['Number_Int'].tolist()
                selected_numbers = all_numbers
        else:
            all_numbers = df['Number_Int'].tolist()
            selected_numbers = all_numbers
    else:
        all_numbers = df['Number_Int'].tolist()
        selected_numbers = all_numbers

    # *** LOGIC DIMENSION MỚI - SỬ DỤNG SELECTED_NUMBERS ***
    length_number = ""
    width_number = ""
    height_number = ""

    # Đếm tần suất của từng số - SỬ DỤNG Counter ĐÃ IMPORT
    number_counts = Counter(selected_numbers)
    unique_numbers = sorted(list(set(selected_numbers)), reverse=True)

    if len(unique_numbers) == 1:
        # Chỉ có 1 loại số: L = W = H
        length_number = str(unique_numbers[0])
        width_number = str(unique_numbers[0])
        height_number = str(unique_numbers[0])

    elif len(unique_numbers) == 2:
        # Có 2 loại số
        larger_num = unique_numbers[0]
        smaller_num = unique_numbers[1]
        
        larger_count = number_counts[larger_num]
        smaller_count = number_counts[smaller_num]
        
        if larger_count >= 2:
            # Số lớn xuất hiện >= 2 lần: L=W=số lớn, H=số nhỏ
            length_number = str(larger_num)
            width_number = str(larger_num)
            height_number = str(smaller_num)
        elif smaller_count >= 2:
            # Số nhỏ xuất hiện >= 2 lần: L=số lớn, W=H=số nhỏ
            length_number = str(larger_num)
            width_number = str(smaller_num)
            height_number = str(smaller_num)
        else:
            # Mỗi số xuất hiện 1 lần: L=số lớn, W=H=số nhỏ
            length_number = str(larger_num)
            width_number = str(smaller_num)
            height_number = str(smaller_num)

    elif len(unique_numbers) >= 3:
        # *** LOGIC CHO 3+ LOẠI SỐ ***
        
        # Xử lý trường hợp có GRAIN
        if grain_orientation in ['Horizontal', 'Vertical']:
            # Với GRAIN, vẫn ưu tiên số lớn nhất làm chiều dài
            length_number = str(unique_numbers[0])
            width_number = str(unique_numbers[1])
            height_number = str(unique_numbers[2])
            
        else:
            # Không có GRAIN → logic tiêu chuẩn
            # Kiểm tra pattern lặp lại
            repeated_numbers = [num for num, count in number_counts.items() if count >= 2]
            
            if repeated_numbers:
                # Có số lặp lại
                main_repeated = max(repeated_numbers)  # Số lặp lớn nhất
                repeated_count = number_counts[main_repeated]
                
                if main_repeated == unique_numbers[0]:  # Số lớn nhất bị lặp
                    if repeated_count >= 2:
                        # Pattern: 504,504,9 → L=504, W=504, H=9
                        length_number = str(main_repeated)
                        width_number = str(main_repeated)
                        height_number = str(unique_numbers[1])  # Số lớn thứ 2
                    else:
                        # Fallback
                        length_number = str(unique_numbers[0])
                        width_number = str(unique_numbers[1])
                        height_number = str(unique_numbers[2])
                else:
                    # Số nhỏ hơn bị lặp: L=số lớn, W=H=số lặp
                    length_number = str(unique_numbers[0])
                    width_number = str(main_repeated)
                    height_number = str(main_repeated)
            else:
                # Không có số lặp, 3+ số khác nhau
                if len(unique_numbers) == 5:
                    # Trường hợp 5 số: L=lớn nhất, W=gần nhỏ nhất, H=nhỏ nhất
                    length_number = str(unique_numbers[0])
                    width_number = str(unique_numbers[-2])
                    height_number = str(unique_numbers[-1])
                else:
                    # Trường hợp 3-4 số: L=lớn nhất, W=giữa, H=nhỏ nhất
                    length_number = str(unique_numbers[0])
                    width_number = str(unique_numbers[1])
                    height_number = str(unique_numbers[-1])

    # Lấy filename và thông tin khác
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
# STREAMLIT APP MAIN - SIMPLIFIED VERSION
# =============================================================================

def main():
    st.title("🔍 PDF Number Extraction Tool")
    st.markdown("---")
    
    # Upload files
    uploaded_files = st.file_uploader(
        "Upload PDF files", 
        type=['pdf'], 
        accept_multiple_files=True,
        help="Select one or more PDF files to process"
    )
    
    if uploaded_files:
        st.success(f"Uploaded {len(uploaded_files)} file(s)")
        
        if st.button("🚀 Process Files", type="primary"):
            # Initialize result arrays
            main_table_results = []  # Cho bảng chính
            secondary_table_results = []  # Cho bảng phụ
            
            # Progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # XỬ LÝ TỪNG FILE RIÊNG BIỆT
            for file_idx, uploaded_file in enumerate(uploaded_files):
                filename = uploaded_file.name
                progress = (file_idx + 1) / len(uploaded_files)
                progress_bar.progress(progress)
                status_text.text(f"Processing {filename}...")
                
                # Read PDF from uploaded file
                pdf_bytes = uploaded_file.read()
                
                with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                    total_pages = len(pdf.pages)
                    
                    if total_pages == 0:
                        continue
                    
                    # *** CHỈ XỬ LÝ TRANG ĐẦU TIÊN ***
                    page = pdf.pages[0]
                    
                    # Trích xuất thông tin profile
                    profile_info = extract_profile_from_page(page)
                    
                    # Trích xuất thông tin FOIL classification và detail
                    foil_classification, foil_detail = extract_foil_classification_with_detail(page)
                    
                    # Trích xuất thông tin EDGEBAND classification và detail
                    edgeband_classification, edgeband_detail = extract_edgeband_classification_with_detail(page)
                    
                    # *** CẬP NHẬT: Trích xuất thông tin LAMINATE classification với logic mới - ĐỂ TRỐNG NẾU CHỈ CÓ 1 KEYWORD ***
                    laminate_classification, laminate_detail = extract_laminate_classification_with_detail(page)
                    
                    # Sử dụng phương pháp trích xuất mới với font frequency = 3 (CHO BẢNG CHÍNH)
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
                            "File": filename,
                            "Number": str(number),
                            "Font Name": fontname,
                            "Font Weight": font_weight,
                            "Orientation": orientation,
                            "Number_Int": number,
                            "Profile": profile_info,
                            "FOIL": foil_classification,
                            "EDGEBAND": edgeband_classification,
                            "Laminate": laminate_classification,  # *** SỬ DỤNG LOGIC MỚI - ĐỂ TRỐNG NẾU CHỈ CÓ 1 KEYWORD ***
                            "Index": i+1
                        })
                    
                    # Xử lý kết quả cho BẢNG PHỤ (tất cả số hợp lệ) - METRICS ĐÃ XOAY TẠI NGUỒN
                    file_secondary_results = []
                    for i, number_info in enumerate(all_valid_numbers):
                        file_secondary_results.append({
                            "File": filename,
                            "Valid Number": number_info['number'],
                            "Font Name": number_info['fontname'],
                            "Font Weight": number_info['font_weight'],
                            "Orientation": number_info['orientation'],
                            "Position_X": round(number_info['x_pos'], 1),
                            "Position_Y": round(number_info['y_pos'], 1),
                            "Chars_Count": number_info['chars_count'],
                            # 8 CHỈ SỐ KHÁC BIỆT (ĐÃ XOAY TẠI NGUỒN)
                            "Font_Size": number_info['font_size'],
                            "Char_Width": number_info['char_width'],
                            "Char_Height": number_info['char_height'],
                            "Density_Score": number_info['density_score'],
                            "Distance_Origin": number_info['distance_from_origin'],
                            "Aspect_Ratio": number_info['aspect_ratio'],
                            "Char_Spacing": number_info['char_spacing'],
                            "Text_Angle": number_info['text_angle'],
                            "Index": i+1,
                            "Page": page  # Lưu page để tìm GRAIN
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
                        
                        # *** MỚI: Tìm group có score cao nhất VÀ có ít nhất 3 thành viên ***
                        group_sizes = df_file_secondary.groupby('Group').size()
                        valid_groups = group_sizes[group_sizes >= 3].index.tolist()
                        
                        if valid_groups:
                            group_scores = df_file_secondary[df_file_secondary['Group'].isin(valid_groups)].groupby('Group')['SCORE'].first().sort_values(ascending=False)
                            
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
            
            # Clear progress
            progress_bar.empty()
            status_text.empty()
            
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
                
                # *** CHỈ HIỂN THỊ BẢNG CHÍNH ***
                st.markdown("---")
                st.markdown("## 📊 Results")
                
                st.dataframe(final_summary, use_container_width=True)
                
                # *** DOWNLOAD BUTTON CHO EXCEL ***
                st.markdown("---")
                
                # Create Excel file in memory
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    final_summary.to_excel(writer, sheet_name='Results', index=False)
                    
                excel_data = output.getvalue()
                
                st.download_button(
                    label="📋 Download Excel",
                    data=excel_data,
                    file_name="dimension_summary.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            else:
                st.warning("No data to display")
                
                # Display empty table
                empty_main = pd.DataFrame(columns=["Drawing#", "Length (mm)", "Width (mm)", "Height (mm)", "Laminate", "FOIL", "EDGEBAND", "Profile"])
                st.dataframe(empty_main, use_container_width=True)

if __name__ == "__main__":
    main()

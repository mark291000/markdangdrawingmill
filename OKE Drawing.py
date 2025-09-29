import streamlit as st
import pdfplumber
import pandas as pd
import re
import numpy as np
from collections import Counter
import math
import io

# =============================================================================
# ENHANCED NUMBER EXTRACTION WITH IMPROVED DECIMAL HANDLING
# =============================================================================

def reverse_number_string(number_string):
    """Đảo ngược chuỗi số"""
    return number_string[::-1]

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
    """Kiểm tra font name có hợp lệ không - BỔ SUNG UYKZBA+Arial-Black"""
    valid_fonts = ['CIDFont+F4', 'CIDFont+F3', 'CIDFont+F2', 'CIDFont+F1', 'F4', 'F3', 'F2', 'F1', 'UYKZBA+Arial-Black']
    return fontname in valid_fonts or any(fontname.endswith(f) for f in valid_fonts)

def get_font_priority(fontname):
    """Trả về độ ưu tiên của font - SỐ CÀNG CAO CÀNG ƯU TIÊN"""
    if 'CIDFont+F3' in fontname:
        return 6  # Ưu tiên cao nhất
    elif 'CIDFont+F2' in fontname:
        return 5
    elif 'CIDFont+F1' in fontname:
        return 4
    elif 'F3' in fontname:
        return 3
    elif 'F2' in fontname:
        return 2
    elif 'F1' in fontname:
        return 1
    elif 'CIDFont+F4' in fontname:
        return 0  # F4 có ưu tiên thấp nhất
    elif 'F4' in fontname:
        return 0
    elif 'UYKZBA+Arial-Black' in fontname:
        return -1  # Ưu tiên thấp nhất, chỉ dùng khi không có F nào
    else:
        return -2  # Không hợp lệ

def format_number_display(number):
    """Format số để hiển thị - loại bỏ .0 cho số nguyên"""
    if isinstance(number, float) and number.is_integer():
        return str(int(number))
    elif isinstance(number, float):
        # Làm tròn đến 1 chữ số thập phân và loại bỏ .0
        formatted = f"{number:.1f}"
        if formatted.endswith('.0'):
            return str(int(number))
        return formatted
    else:
        return str(number)

def process_character_for_decimal_improved(chars):
    """Xử lý các ký tự để tìm số thập phân - CẢI TIẾN"""
    decimal_numbers = []
    
    # Sắp xếp chars theo vị trí
    sorted_chars = sorted(chars, key=lambda c: (c['top'], c['x0']))
    
    # Tạo text từ các ký tự liền kề
    i = 0
    while i < len(sorted_chars):
        current_text = sorted_chars[i]['text']
        current_chars = [sorted_chars[i]]
        j = i + 1
        
        # Kiểm tra các ký tự liền kề để tạo thành số
        while j < len(sorted_chars):
            next_char = sorted_chars[j]
            current_char = sorted_chars[j-1]
            
            # Kiểm tra khoảng cách giữa các ký tự - THU HẸP KHOẢNG CÁCH
            distance = math.sqrt(
                (current_char['x0'] - next_char['x0'])**2 +
                (current_char['top'] - next_char['top'])**2
            )
            
            # GIẢM KHOẢNG CÁCH GHÉP TỪ 15 XUỐNG 8 ĐỂ CHÍNH XÁC HƠN
            if distance < 8:  # Ký tự liền kề chặt chẽ
                current_text += next_char['text']
                current_chars.append(next_char)
                j += 1
            else:
                break
        
        # XỬ LÝ SỐ THẬP PHÂN CHÍNH XÁC
        # Tìm pattern số thập phân chính xác (chỉ 1 dấu chấm)
        decimal_pattern = r'^\d+\.\d+$'
        if re.match(decimal_pattern, current_text):
            try:
                decimal_value = float(current_text)
                if 1 <= decimal_value <= 3500:
                    decimal_numbers.append(decimal_value)
            except:
                pass
        
        i = j if j > i + 1 else i + 1
    
    return decimal_numbers

def extract_numbers_from_specific_font_improved(page, target_font):
    """Trích xuất số từ một font cụ thể - CẢI THIỆN XỬ LÝ SỐ THẬP PHÂN"""
    numbers = []
    orientations = {}
    font_info = {}

    try:
        chars = page.chars
        
        # Lọc chars theo font target (bao gồm cả chữ số và dấu chấm)
        target_chars = [c for c in chars if c.get('fontname', 'Unknown') == target_font and (c['text'].isdigit() or c['text'] == '.')]
        
        if not target_chars:
            return numbers, orientations, font_info

        # XỬ LÝ SỐ THẬP PHÂN TRƯỚC VỚI THUẬT TOÁN CẢI TIẾN
        decimal_numbers = process_character_for_decimal_improved(target_chars)
        for decimal_num in decimal_numbers:
            formatted_num = format_number_display(decimal_num)
            numbers.append(decimal_num)  # Giữ nguyên giá trị số
            orientations[f"{decimal_num}_{len(numbers)}"] = 'Decimal'
            font_info[f"{decimal_num}_{len(numbers)}"] = {
                'chars': [],
                'fontname': target_font,
                'value': decimal_num,
                'display': formatted_num  # Thêm format hiển thị
            }

        # XỬ LÝ SỐ NGUYÊN (chỉ ký tự số)
        digit_chars = [c for c in target_chars if c['text'].isdigit()]

        if digit_chars:
            char_groups = create_character_groups_improved(digit_chars, target_font)
            extracted_numbers = [num for num in decimal_numbers]  # Tránh trùng lặp

            for group in char_groups:
                if len(group) == 1:
                    try:
                        num_value = int(group[0]['text'])
                        fontname = group[0].get('fontname', 'Unknown')
                        
                        # CHỈ LẤY SỐ CỦA FONT MỤC TIÊU VÀ TRÁNH TRÙNG LẶP
                        if (1 <= num_value <= 3500 and fontname == target_font and num_value not in extracted_numbers):
                            numbers.append(num_value)
                            orientations[f"{num_value}_{len(numbers)}"] = 'Single'
                            font_info[f"{num_value}_{len(numbers)}"] = {
                                'chars': group,
                                'fontname': fontname,
                                'value': num_value,
                                'display': format_number_display(num_value)
                            }
                            extracted_numbers.append(num_value)
                    except:
                        continue
                else:
                    result = process_character_group_smart(group, extracted_numbers, target_font)
                    if result:
                        number, orientation = result
                        if number not in extracted_numbers:  # Tránh trùng lặp
                            numbers.append(number)
                            orientations[f"{number}_{len(numbers)}"] = orientation
                            fonts = [ch.get("fontname", "Unknown") for ch in group]
                            fontname = Counter(fonts).most_common(1)[0][0] if fonts else "Unknown"
                            font_info[f"{number}_{len(numbers)}"] = {
                                'chars': group,
                                'fontname': fontname,
                                'value': number,
                                'display': format_number_display(number)
                            }
                            extracted_numbers.append(number)

    except Exception as e:
        pass

    return numbers, orientations, font_info

def extract_numbers_with_complete_logic(page):
    """
    LOGIC HOÀN CHỈNH CẬP NHẬT:
    1. Nếu đã nâng lên F cao nhất nhưng vẫn chỉ có 1 number thì ghi cho Length (mm), 2 number thì ghi cho Length (mm), Width (mm)
    2. Nếu không có font name F nào thì lấy những number thuộc fontname UYKZBA+Arial-Black
    """
    try:
        chars = page.chars
        all_chars = [c for c in chars if c['text'].isdigit() or c['text'] == '.']

        if not all_chars:
            return [], {}, {}

        # Lấy tất cả font có trong page
        all_fonts = list(set([c.get('fontname', 'Unknown') for c in all_chars]))
        valid_fonts = [f for f in all_fonts if is_valid_font(f)]
        
        # Tách riêng F fonts và Arial-Black font
        f_fonts = [f for f in valid_fonts if any(x in f for x in ['F1', 'F2', 'F3', 'F4'])]
        arial_black_fonts = [f for f in valid_fonts if 'UYKZBA+Arial-Black' in f]
        
        chosen_font = None
        
        # BƯỚC 1: ƯU TIÊN F FONTS TRƯỚC
        if f_fonts:
            # Phân loại font theo loại
            f1_fonts = [f for f in f_fonts if 'F1' in f]
            f2_fonts = [f for f in f_fonts if 'F2' in f]
            f3_fonts = [f for f in f_fonts if 'F3' in f]
            f4_fonts = [f for f in f_fonts if 'F4' in f]

            # Case 1: Chỉ có F1 và F2 → ưu tiên F2
            if f1_fonts and f2_fonts and not f3_fonts and not f4_fonts:
                chosen_font = max(f2_fonts, key=get_font_priority)
            
            # Case 2: Chỉ có F2 và F3 → kiểm tra F3, nếu không đủ 3 số thì nâng lên F4
            elif f2_fonts and f3_fonts and not f1_fonts and not f4_fonts:
                f3_font = max(f3_fonts, key=get_font_priority)
                numbers_f3, _, _ = extract_numbers_from_specific_font_improved(page, f3_font)
                
                if len(numbers_f3) >= 3:
                    chosen_font = f3_font  # F3 đủ 3 số
                else:
                    # F3 không đủ 3 số, cần mở rộng lên F4
                    if f4_fonts:
                        chosen_font = max(f4_fonts, key=get_font_priority)
                    else:
                        chosen_font = f3_font  # Không có F4, dùng F3
            
            # Case 3: Có F2 và F3 và cả F4 → kiểm tra F3, nếu không đủ 3 số thì nâng lên F4
            elif f2_fonts and f3_fonts and f4_fonts:
                f3_font = max(f3_fonts, key=get_font_priority)
                numbers_f3, _, _ = extract_numbers_from_specific_font_improved(page, f3_font)
                
                if len(numbers_f3) >= 3:
                    chosen_font = f3_font  # F3 đủ 3 số
                else:
                    chosen_font = max(f4_fonts, key=get_font_priority)  # Nâng lên F4
            
            # Case 4: Chỉ có một loại font
            elif f3_fonts and not f2_fonts and not f1_fonts:
                # Chỉ có F3 → kiểm tra F3, nếu không đủ 3 số và có F4 thì nâng lên F4
                f3_font = max(f3_fonts, key=get_font_priority)
                numbers_f3, _, _ = extract_numbers_from_specific_font_improved(page, f3_font)
                
                if len(numbers_f3) >= 3:
                    chosen_font = f3_font
                elif f4_fonts:
                    chosen_font = max(f4_fonts, key=get_font_priority)
                else:
                    chosen_font = f3_font
            
            elif f2_fonts and not f3_fonts and not f1_fonts:
                # Chỉ có F2 → kiểm tra F2, nếu không đủ 3 số và có F4 thì nâng lên F4
                f2_font = max(f2_fonts, key=get_font_priority)
                numbers_f2, _, _ = extract_numbers_from_specific_font_improved(page, f2_font)
                
                if len(numbers_f2) >= 3:
                    chosen_font = f2_font
                elif f4_fonts:
                    chosen_font = max(f4_fonts, key=get_font_priority)
                else:
                    chosen_font = f2_font
            
            elif f1_fonts and not f2_fonts and not f3_fonts:
                chosen_font = max(f1_fonts, key=get_font_priority)
            
            elif f4_fonts and not f1_fonts and not f2_fonts and not f3_fonts:
                chosen_font = max(f4_fonts, key=get_font_priority)
            
            # Case 5: Có nhiều loại font khác → ưu tiên F3 > F2 > F1, kiểm tra mở rộng F4
            else:
                if f3_fonts:
                    f3_font = max(f3_fonts, key=get_font_priority)
                    numbers_f3, _, _ = extract_numbers_from_specific_font_improved(page, f3_font)
                    
                    if len(numbers_f3) >= 3:
                        chosen_font = f3_font
                    elif f4_fonts:
                        chosen_font = max(f4_fonts, key=get_font_priority)
                    else:
                        chosen_font = f3_font
                elif f2_fonts:
                    f2_font = max(f2_fonts, key=get_font_priority)
                    numbers_f2, _, _ = extract_numbers_from_specific_font_improved(page, f2_font)
                    
                    if len(numbers_f2) >= 3:
                        chosen_font = f2_font
                    elif f4_fonts:
                        chosen_font = max(f4_fonts, key=get_font_priority)
                    else:
                        chosen_font = f2_font
                elif f1_fonts:
                    chosen_font = max(f1_fonts, key=get_font_priority)
                else:
                    chosen_font = max(f_fonts, key=get_font_priority)
        
        # BƯỚC 2: NẾU KHÔNG CÓ F FONTS NÀO, DÙNG ARIAL-BLACK
        elif arial_black_fonts:
            chosen_font = arial_black_fonts[0]  # Chọn Arial-Black font
        
        # BƯỚC 3: TRÍCH XUẤT SỐ TỪ FONT ĐÃ CHỌN
        if chosen_font:
            final_numbers, final_orientations, final_font_info = extract_numbers_from_specific_font_improved(page, chosen_font)
            
            # Cập nhật font name trong kết quả
            for key in final_font_info:
                final_font_info[key]['fontname'] = chosen_font
                
            return final_numbers, final_orientations, final_font_info
        
        return [], {}, {}

    except Exception as e:
        return [], {}, {}

def create_character_groups_improved(digit_chars, target_font):
    """Tạo các nhóm ký tự - CẢI THIỆN XỬ LÝ SỐ DỌC ĐẦY ĐỦ"""
    char_groups = []
    used_chars = set()

    # Lọc chỉ giữ ký tự từ font mục tiêu
    valid_digit_chars = [c for c in digit_chars if c.get('fontname', 'Unknown') == target_font]
    
    if not valid_digit_chars:
        return char_groups

    sorted_chars = sorted(valid_digit_chars, key=lambda c: (c['top'], c['x0']))

    for i, base_char in enumerate(sorted_chars):
        if id(base_char) in used_chars:
            continue

        current_group = [base_char]
        used_chars.add(id(base_char))

        # MỞ RỘNG VÙNG GOM ĐỂ BẮT SỐ DỌC ĐẦY ĐỦ
        for j, other_char in enumerate(sorted_chars):
            if i == j or id(other_char) in used_chars:
                continue

            if should_group_characters(base_char, other_char, current_group, target_font):
                current_group.append(other_char)
                used_chars.add(id(other_char))

        if len(current_group) >= 1:
            char_groups.append(current_group)

    return char_groups

def should_group_characters(base_char, other_char, current_group, target_font):
    """Xác định xem 2 ký tự có nên được nhóm lại không - CẢI THIỆN XỬ LÝ SỐ DỌC"""
    try:
        # Kiểm tra font - chỉ nhóm các ký tự cùng font mục tiêu
        base_font = base_char.get('fontname', 'Unknown')
        other_font = other_char.get('fontname', 'Unknown')
        
        if not (base_font == target_font and other_font == target_font):
            return False
        
        # TĂNG KHOẢNG CÁCH CHO PHÉP ĐỂ BẮT SỐ DỌC ĐẦY ĐỦ
        distance = math.sqrt(
            (base_char['x0'] - other_char['x0'])**2 +
            (base_char['top'] - other_char['top'])**2
        )

        # Tăng khoảng cách cho phép
        if distance > 60:  # Tăng từ 50 lên 60
            return False

        if len(current_group) > 1:
            group_x_span = max(c['x0'] for c in current_group) - min(c['x0'] for c in current_group)
            group_y_span = max(c['top'] for c in current_group) - min(c['top'] for c in current_group)

            is_group_vertical = group_y_span > group_x_span * 1.2

            if is_group_vertical:
                group_x_center = sum(c['x0'] for c in current_group) / len(current_group)
                if abs(other_char['x0'] - group_x_center) > 20:  # Tăng từ 15 lên 20
                    return False
            else:
                group_y_center = sum(c['top'] for c in current_group) / len(current_group)
                if abs(other_char['top'] - group_y_center) > 15:  # Tăng từ 10 lên 15
                    return False

        return True

    except Exception:
        return False

def process_character_group_smart(group, extracted_numbers, target_font):
    """Xử lý nhóm ký tự thông minh - CẢI THIỆN XỬ LÝ SỐ DỌC"""
    try:
        if len(group) < 2:
            return None
        
        # Kiểm tra font mục tiêu cho cả nhóm
        fonts = [ch.get("fontname", "Unknown") for ch in group]
        if not all(font == target_font for font in fonts):
            return None

        x_positions = [c['x0'] for c in group]
        y_positions = [c['top'] for c in group]

        x_span = max(x_positions) - min(x_positions)
        y_span = max(y_positions) - min(y_positions)

        is_vertical = y_span > x_span * 1.2

        if is_vertical:
            vertical_sorted = sorted(group, key=lambda c: c['top'])
            v_text = "".join([c['text'] for c in vertical_sorted])

            candidates = []

            # XỬ LÝ SỐ DỌC - ĐẢM BẢO LẤY ĐẦY ĐỦ CÁC CHỮ SỐ
            try:
                num_original = int(v_text)
                if 1 <= num_original <= 3500:
                    candidates.append((num_original, 'Vertical'))
            except:
                pass

            try:
                reversed_v_text = reverse_number_string(v_text)
                num_reversed = int(reversed_v_text)
                if 1 <= num_reversed <= 3500:
                    candidates.append((num_reversed, 'Vertical'))
            except:
                pass

            if len(candidates) > 1:
                for candidate in candidates:
                    if candidate[0] == int(reverse_number_string(v_text)):
                        return candidate
            elif len(candidates) == 1:
                return candidates[0]

        else:
            horizontal_sorted = sorted(group, key=lambda c: c['x0'])
            h_text = "".join([c['text'] for c in horizontal_sorted])

            try:
                num_value = int(h_text)
                if 1 <= num_value <= 3500:
                    return (num_value, 'Horizontal')
            except:
                pass

        return None

    except Exception:
        return None

def create_dimension_summary_improved(df):
    """Tạo bảng tóm tắt - CẬP NHẬT VỚI FORMAT SỐ CẢI TIẾN"""
    if len(df) == 0:
        return pd.DataFrame(columns=["Drawing#", "Length (mm)", "Width (mm)", "Height (mm)", "FOIL", "EDGEBAND", "Profile"])
    
    # Lấy tất cả số và sắp xếp theo thứ tự giảm dần (KHÔNG loại bỏ trùng lặp)
    all_numbers = df['Number_Int'].tolist()
    sorted_numbers = sorted(all_numbers, reverse=True)  # Từ lớn đến nhỏ, GIỮ NGUYÊN SỐ TRÙNG
    
    # Khởi tạo các giá trị dimension với format cải tiến
    length_number = ""
    width_number = ""
    height_number = ""
    
    # CẬP NHẬT LOGIC: ƯU TIÊN ĐIỀN TỪ TRÁI QUA PHẢI - CHẤP NHẬN SỐ TRÙNG
    if len(sorted_numbers) == 1:
        # Chỉ có 1 số: chỉ điền Length
        length_number = format_number_display(sorted_numbers[0])
        # Width và Height để trống
        
    elif len(sorted_numbers) == 2:
        # Có 2 số: điền Length và Width (có thể trùng nhau)
        length_number = format_number_display(sorted_numbers[0])    # Số đầu tiên (lớn nhất hoặc bằng)
        width_number = format_number_display(sorted_numbers[1])     # Số thứ hai
        # Height để trống
        
    elif len(sorted_numbers) >= 3:
        # Có 3+ số: điền đầy đủ L, W, H (chấp nhận trùng lặp)
        length_number = format_number_display(sorted_numbers[0])    # Số đầu tiên (lớn nhất)
        width_number = format_number_display(sorted_numbers[1])     # Số thứ hai 
        height_number = format_number_display(sorted_numbers[2])    # Số thứ ba
    
    # Lấy filename
    filename = df.iloc[0]['File']
    drawing_name = filename.replace('.pdf', '') if filename.endswith('.pdf') else filename
    
    # Lấy thông tin profile, FOIL, EDGEBAND
    profile_info = df.iloc[0]['Profile'] if 'Profile' in df.columns else ""
    foil_info = df.iloc[0]['FOIL'] if 'FOIL' in df.columns else ""
    edgeband_info = df.iloc[0]['EDGEBAND'] if 'EDGEBAND' in df.columns else ""
    
    result_df = pd.DataFrame({
        "Drawing#": [drawing_name],
        "Length (mm)": [length_number],
        "Width (mm)": [width_number], 
        "Height (mm)": [height_number],
        "FOIL": [foil_info],
        "EDGEBAND": [edgeband_info],
        "Profile": [profile_info]
    })
    
    return result_df

# =============================================================================
# STREAMLIT APP
# =============================================================================

def main():
    st.title("PDF Processing for Furniture Dimensions")
    st.write("Upload PDF files để trích xuất thông tin kích thước và classification")
    
    # File uploader
    uploaded_files = st.file_uploader(
        "Chọn file PDF", 
        type=['pdf'], 
        accept_multiple_files=True
    )
    
    if uploaded_files:
        if st.button("Xử lý PDF Files"):
            results = []
            
            # Progress bar
            progress_bar = st.progress(0)
            total_files = len(uploaded_files)
            
            for idx, uploaded_file in enumerate(uploaded_files):
                try:
                    # Update progress
                    progress_bar.progress((idx + 1) / total_files)
                    
                    # Read PDF
                    with pdfplumber.open(io.BytesIO(uploaded_file.read())) as pdf:
                        total_pages = len(pdf.pages)

                        if total_pages == 0:
                            continue

                        page = pdf.pages[0]

                        # Trích xuất thông tin profile
                        profile_info = extract_profile_from_page(page)
                        
                        # Trích xuất thông tin FOIL classification và detail
                        foil_classification, foil_detail = extract_foil_classification_with_detail(page)
                        
                        # Trích xuất thông tin EDGEBAND classification và detail
                        edgeband_classification, edgeband_detail = extract_edgeband_classification_with_detail(page)

                        # SỬ DỤNG LOGIC HOÀN CHỈNH CẬP NHẬT VỚI DECIMAL IMPROVED
                        char_numbers, char_orientations, font_info = extract_numbers_with_complete_logic(page)

                        if not char_numbers:
                            continue

                        # Xử lý kết quả
                        for i, number in enumerate(char_numbers):
                            key = f"{number}_{i+1}"
                            orientation = char_orientations.get(key, 'Horizontal')
                            fontname = font_info.get(key, {}).get('fontname', 'Unknown')
                            display_number = font_info.get(key, {}).get('display', format_number_display(number))
                            
                            # Lưu vào kết quả chính
                            results.append({
                                "File": uploaded_file.name,
                                "Number": display_number,  # Sử dụng format hiển thị
                                "Font Name": fontname,
                                "Orientation": orientation,
                                "Number_Int": number,  # Giữ nguyên giá trị số để sort
                                "Profile": profile_info,
                                "FOIL": foil_classification,
                                "EDGEBAND": edgeband_classification,
                                "Index": i+1
                            })
                
                except Exception as e:
                    st.error(f"Lỗi khi xử lý file {uploaded_file.name}: {e}")
            
            # Clear progress bar
            progress_bar.empty()
            
            # Tạo DataFrame và hiển thị kết quả
            if results:
                df_all = pd.DataFrame(results).reset_index(drop=True)
                
                # Lọc chỉ giữ font hợp lệ
                df_all = df_all[df_all["Font Name"].apply(is_valid_font)].reset_index(drop=True)
                
                if not df_all.empty:
                    df_final = df_all.copy()
                    df_final = df_final.drop(columns=["Index"])
                    
                    # Tạo bảng tóm tắt cho từng file
                    summary_results = []
                    for file_group in df_final.groupby("File"):
                        filename, file_data = file_group
                        summary = create_dimension_summary_improved(file_data)
                        summary_results.append(summary)
                    
                    # Kết hợp tất cả kết quả
                    final_summary = pd.concat(summary_results, ignore_index=True) if summary_results else pd.DataFrame(columns=["Drawing#", "Length (mm)", "Width (mm)", "Height (mm)", "FOIL", "EDGEBAND", "Profile"])
                    
                    # CHỈ HIỂN THỊ BẢNG TÓM TẮT
                    st.subheader("📊 Kết quả - Bảng tóm tắt kích thước")
                    st.dataframe(final_summary, use_container_width=True)
                    
                    # Download button cho bảng tóm tắt - EXCEL
                    excel_buffer = io.BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                        final_summary.to_excel(writer, sheet_name='Dimension Summary', index=False)
                    
                    excel_buffer.seek(0)
                    
                    st.download_button(
                        label="📥 Tải bảng tóm tắt (Excel)",
                        data=excel_buffer.getvalue(),
                        file_name="dimension_summary.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                
                else:
                    st.warning("Không có dữ liệu hợp lệ sau khi lọc font")
                    empty_df = pd.DataFrame(columns=["Drawing#", "Length (mm)", "Width (mm)", "Height (mm)", "FOIL", "EDGEBAND", "Profile"])
                    st.dataframe(empty_df)
            
            else:
                st.warning("Không có dữ liệu để hiển thị")
                empty_df = pd.DataFrame(columns=["Drawing#", "Length (mm)", "Width (mm)", "Height (mm)", "FOIL", "EDGEBAND", "Profile"])
                st.dataframe(empty_df)

if __name__ == "__main__":
    main()

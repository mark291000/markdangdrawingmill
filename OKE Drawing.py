import streamlit as st
import pdfplumber
import pandas as pd
import re
import numpy as np
from collections import Counter
import math
import io

# =============================================================================
# ENHANCED NUMBER EXTRACTION FROM NEW CODE
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
    """Kiểm tra font name có hợp lệ không - CHẤP NHẬN CIDFont+F1, CIDFont+F2, CIDFont+F3, CIDFont+F4, F1, F2, F3, F4"""
    valid_fonts = ['CIDFont+F4', 'CIDFont+F3', 'CIDFont+F2', 'CIDFont+F1', 'F4', 'F3', 'F2', 'F1']
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
    else:
        return -1  # Không hợp lệ

def extract_numbers_from_specific_font(page, target_font):
    """Trích xuất số từ một font cụ thể"""
    numbers = []
    orientations = {}
    font_info = {}

    try:
        chars = page.chars
        digit_chars = [c for c in chars if c['text'].isdigit()]

        if not digit_chars:
            return numbers, orientations, font_info

        char_groups = create_character_groups_improved(digit_chars, target_font)
        extracted_numbers = []

        for group in char_groups:
            if len(group) == 1:
                try:
                    num_value = int(group[0]['text'])
                    fontname = group[0].get('fontname', 'Unknown')
                    
                    # CHỈ LẤY SỐ CỦA FONT MỤC TIÊU
                    if (1 <= num_value <= 3500 and fontname == target_font):
                        
                        numbers.append(num_value)
                        orientations[f"{num_value}_{len(numbers)}"] = 'Single'
                        font_info[f"{num_value}_{len(numbers)}"] = {
                            'chars': group,
                            'fontname': fontname,
                            'value': num_value
                        }
                        extracted_numbers.append(num_value)
                except:
                    continue
            else:
                result = process_character_group_smart(group, extracted_numbers, target_font)
                if result:
                    number, orientation = result
                    numbers.append(number)
                    orientations[f"{number}_{len(numbers)}"] = orientation
                    fonts = [ch.get("fontname", "Unknown") for ch in group]
                    fontname = Counter(fonts).most_common(1)[0][0] if fonts else "Unknown"
                    font_info[f"{number}_{len(numbers)}"] = {
                        'chars': group,
                        'fontname': fontname,
                        'value': number
                    }
                    extracted_numbers.append(number)

    except Exception as e:
        pass

    return numbers, orientations, font_info

def extract_numbers_with_smart_font_priority(page):
    """METHOD: Trích xuất số với logic ưu tiên font thông minh"""
    try:
        chars = page.chars
        digit_chars = [c for c in chars if c['text'].isdigit()]

        if not digit_chars:
            return [], {}, {}

        # Lấy tất cả font có trong page
        all_fonts = list(set([c.get('fontname', 'Unknown') for c in digit_chars]))
        valid_fonts = [f for f in all_fonts if is_valid_font(f)]
        
        if not valid_fonts:
            return [], {}, {}

        # Phân loại font theo loại
        f1_fonts = [f for f in valid_fonts if 'F1' in f]
        f2_fonts = [f for f in valid_fonts if 'F2' in f]
        f3_fonts = [f for f in valid_fonts if 'F3' in f]
        f4_fonts = [f for f in valid_fonts if 'F4' in f]

        # LOGIC ƯU TIÊN MỚI
        chosen_font = None
        
        # Trường hợp 1: Chỉ có F1 và F2 → ưu tiên F2
        if f1_fonts and f2_fonts and not f3_fonts and not f4_fonts:
            chosen_font = max(f2_fonts, key=get_font_priority)
        
        # Trường hợp 2: Chỉ có F2 và F3 → ưu tiên F3
        elif f2_fonts and f3_fonts and not f1_fonts and not f4_fonts:
            # Thử F3 trước
            f3_font = max(f3_fonts, key=get_font_priority)
            numbers_f3, orientations_f3, font_info_f3 = extract_numbers_from_specific_font(page, f3_font)
            unique_numbers_f3 = list(set(numbers_f3)) if numbers_f3 else []
            
            if len(unique_numbers_f3) >= 3:
                # F3 đủ 3 số, sử dụng F3
                chosen_font = f3_font
            else:
                # F3 không đủ 3 số, nâng lên F4
                if f4_fonts:
                    chosen_font = max(f4_fonts, key=get_font_priority)
                else:
                    # Không có F4, sử dụng F3 hoặc F2
                    chosen_font = f3_font if numbers_f3 else max(f2_fonts, key=get_font_priority)
        
        # Trường hợp 3: Có cả F1, F2, F3 → ưu tiên F3
        elif f1_fonts and f2_fonts and f3_fonts:
            chosen_font = max(f3_fonts, key=get_font_priority)
        
        # Trường hợp 4: Chỉ có F3 → sử dụng F3
        elif f3_fonts and not f1_fonts and not f2_fonts:
            chosen_font = max(f3_fonts, key=get_font_priority)
        
        # Trường hợp 5: Chỉ có F2 → sử dụng F2
        elif f2_fonts and not f1_fonts and not f3_fonts:
            chosen_font = max(f2_fonts, key=get_font_priority)
        
        # Trường hợp 6: Chỉ có F1 → sử dụng F1
        elif f1_fonts and not f2_fonts and not f3_fonts:
            chosen_font = max(f1_fonts, key=get_font_priority)
        
        # Trường hợp mặc định: chọn font có priority cao nhất
        else:
            chosen_font = max(valid_fonts, key=get_font_priority)

        # Trích xuất số từ font đã chọn
        if chosen_font:
            final_numbers, final_orientations, final_font_info = extract_numbers_from_specific_font(page, chosen_font)
            
            # Cập nhật font name trong kết quả
            for key in final_font_info:
                final_font_info[key]['fontname'] = chosen_font
                
            return final_numbers, final_orientations, final_font_info
        
        return [], {}, {}

    except Exception as e:
        return [], {}, {}

def create_character_groups_improved(digit_chars, target_font):
    """Tạo các nhóm ký tự - CHỈ GOM CÁC KÝ TỰ CỦA FONT MỤC TIÊU"""
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
    """Xác định xem 2 ký tự có nên được nhóm lại không - CHỈ GOM CÙNG FONT MỤC TIÊU"""
    try:
        # Kiểm tra font - chỉ nhóm các ký tự cùng font mục tiêu
        base_font = base_char.get('fontname', 'Unknown')
        other_font = other_char.get('fontname', 'Unknown')
        
        if not (base_font == target_font and other_font == target_font):
            return False
        
        # Tăng khoảng cách cho phép để bắt số dọc đầy đủ
        distance = math.sqrt(
            (base_char['x0'] - other_char['x0'])**2 +
            (base_char['top'] - other_char['top'])**2
        )

        # TĂNG KHOẢNG CÁCH CHO PHÉP ĐỂ BẮT SỐ DỌC
        if distance > 50:
            return False

        if len(current_group) > 1:
            group_x_span = max(c['x0'] for c in current_group) - min(c['x0'] for c in current_group)
            group_y_span = max(c['top'] for c in current_group) - min(c['top'] for c in current_group)

            is_group_vertical = group_y_span > group_x_span * 1.2

            if is_group_vertical:
                group_x_center = sum(c['x0'] for c in current_group) / len(current_group)
                if abs(other_char['x0'] - group_x_center) > 15:
                    return False
            else:
                group_y_center = sum(c['top'] for c in current_group) / len(current_group)
                if abs(other_char['top'] - group_y_center) > 10:
                    return False

        return True

    except Exception:
        return False

def process_character_group_smart(group, extracted_numbers, target_font):
    """Xử lý nhóm ký tự thông minh - CHỈ XỬ LÝ FONT MỤC TIÊU"""
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

def create_dimension_summary(df):
    """Tạo bảng tóm tắt - WIDTH LÀ SỐ GẦN NHỎ NHẤT"""
    if len(df) == 0:
        return pd.DataFrame(columns=["Drawing#", "Length (mm)", "Width (mm)", "Height (mm)", "FOIL", "EDGEBAND", "Profile"])
    
    # Lấy tất cả số và sắp xếp theo thứ tự giảm dần
    all_numbers = df['Number_Int'].tolist()
    unique_numbers = sorted(list(set(all_numbers)), reverse=True)  # Từ lớn đến nhỏ
    
    # Khởi tạo các giá trị dimension
    length_number = ""
    width_number = ""
    height_number = ""
    
    if len(unique_numbers) == 1:
        # Chỉ có 1 số: L = W = H
        length_number = str(unique_numbers[0])
        width_number = str(unique_numbers[0])
        height_number = str(unique_numbers[0])
        
    elif len(unique_numbers) == 2:
        # Có 2 số: L = số lớn, W = H = số nhỏ
        length_number = str(unique_numbers[0])    # Số lớn nhất
        width_number = str(unique_numbers[1])     # Số nhỏ nhất
        height_number = str(unique_numbers[1])    # Số nhỏ nhất = width
        
    elif len(unique_numbers) >= 3:
        # Có 3+ số: L = lớn nhất, W = gần nhỏ nhất, H = nhỏ nhất
        length_number = str(unique_numbers[0])    # Số lớn nhất
        width_number = str(unique_numbers[-2])    # Số gần nhỏ nhất (thứ 2 từ cuối)
        height_number = str(unique_numbers[-1])   # Số nhỏ nhất
    
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

                        # SỬ DỤNG PHƯƠNG PHÁP MỚI: Logic ưu tiên font thông minh
                        char_numbers, char_orientations, font_info = extract_numbers_with_smart_font_priority(page)

                        if not char_numbers:
                            continue

                        # Xử lý kết quả
                        for i, number in enumerate(char_numbers):
                            key = f"{number}_{i+1}"
                            orientation = char_orientations.get(key, 'Horizontal')
                            fontname = font_info.get(key, {}).get('fontname', 'Unknown')
                            
                            # Lưu vào kết quả chính
                            results.append({
                                "File": uploaded_file.name,
                                "Number": str(number),
                                "Font Name": fontname,
                                "Orientation": orientation,
                                "Number_Int": number,
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
                        summary = create_dimension_summary(file_data)
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

import streamlit as st
import pdfplumber
import re
import pandas as pd
from collections import defaultdict
import os
import tempfile
import io
import math

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="PDF Data Extractor",
    page_icon="📄",
    layout="wide"
)

# --- CÁC HÀM XỬ LÝ CỐT LÕI ---

def extract_page_elements(page):
    """
    Trích xuất các elements cơ bản từ trang PDF
    """
    try:
        chars = page.chars or []
        lines = page.lines or []
        words = page.extract_words(x_tolerance=2, y_tolerance=2) if hasattr(page, 'extract_words') else []
        
        return {
            'chars': chars,
            'lines': lines, 
            'words': words,
            'width': page.width,
            'height': page.height
        }
    except Exception as e:
        st.error(f"Lỗi khi trích xuất elements: {e}")
        return {'chars': [], 'lines': [], 'words': [], 'width': 0, 'height': 0}

def find_dimension_lines(lines, tolerance=2):
    """
    Tìm các đường kích thước ngang và dọc
    """
    horizontal_lines = []
    vertical_lines = []
    
    for line in lines:
        try:
            if abs(line['y0'] - line['y1']) <= tolerance:
                horizontal_lines.append(line)
            elif abs(line['x0'] - line['x1']) <= tolerance:
                vertical_lines.append(line)
        except (KeyError, TypeError):
            continue
            
    return horizontal_lines, vertical_lines

def build_alphanumeric_strings(page_elements):
    """
    Xây dựng danh sách các chuỗi alphanumeric từ words và chars
    """
    alphanumeric_strings = []
    
    # Phương pháp 1: Từ words
    try:
        for word in page_elements['words']:
            text = word['text'].strip()
            has_letter = any(c.isalpha() for c in text)
            has_digit = any(c.isdigit() for c in text)
            
            if has_letter and has_digit and len(text) > 1:
                alphanumeric_strings.append({
                    'text': text,
                    'x0': word['x0'],
                    'x1': word['x1'],
                    'top': word['top'],
                    'bottom': word['bottom'],
                    'method': 'words'
                })
    except Exception:
        pass
    
    # Phương pháp 2: Từ chars (backup)
    try:
        chars = sorted(page_elements['chars'], key=lambda c: (round(c['top'], 1), c['x0']))
        current_string = []
        
        for i, char in enumerate(chars):
            if current_string:
                last_char = current_string[-1]
                # Kiểm tra khoảng cách
                distance_x = char['x0'] - last_char['x1']
                distance_y = abs(char['top'] - last_char['top'])
                
                if distance_x <= 3 and distance_y <= 2:
                    current_string.append(char)
                else:
                    # Xử lý chuỗi hiện tại
                    if len(current_string) > 1:
                        text = ''.join([c['text'] for c in current_string])
                        has_letter = any(c.isalpha() for c in text)
                        has_digit = any(c.isdigit() for c in text)
                        
                        if has_letter and has_digit:
                            alphanumeric_strings.append({
                                'text': text,
                                'x0': min(c['x0'] for c in current_string),
                                'x1': max(c['x1'] for c in current_string),
                                'top': min(c['top'] for c in current_string),
                                'bottom': max(c['bottom'] for c in current_string),
                                'method': 'chars'
                            })
                    current_string = [char]
            else:
                current_string = [char]
        
        # Xử lý chuỗi cuối cùng
        if len(current_string) > 1:
            text = ''.join([c['text'] for c in current_string])
            has_letter = any(c.isalpha() for c in text)
            has_digit = any(c.isdigit() for c in text)
            
            if has_letter and has_digit:
                alphanumeric_strings.append({
                    'text': text,
                    'x0': min(c['x0'] for c in current_string),
                    'x1': max(c['x1'] for c in current_string),
                    'top': min(c['top'] for c in current_string),
                    'bottom': max(c['bottom'] for c in current_string),
                    'method': 'chars'
                })
    except Exception:
        pass
    
    return alphanumeric_strings

def calculate_robust_ink_area(cluster, page):
    """
    Tính toán ink area với nhiều phương pháp fallback
    """
    if not cluster:
        return 0.0
    
    try:
        # Lấy thông tin ký tự đầu tiên
        first_char = cluster[0]
        char_width = first_char['x1'] - first_char['x0']
        char_height = first_char['bottom'] - first_char['top']
        font_size = first_char.get('size', 10)
        
        # Phương pháp 1: Crop và tính ink area
        try:
            padding = 0.5
            bbox = (
                max(0, first_char['x0'] - padding),
                max(0, first_char['top'] - padding),
                min(page.width, first_char['x1'] + padding),
                min(page.height, first_char['bottom'] + padding)
            )
            
            if bbox[2] > bbox[0] and bbox[3] > bbox[1]:
                cropped = page.crop(bbox)
                if cropped:
                    ink_area = 0.0
                    
                    # Từ rects
                    for rect in (cropped.rects or []):
                        if 'width' in rect and 'height' in rect:
                            ink_area += rect['width'] * rect['height']
                    
                    # Từ lines
                    for line in (cropped.lines or []):
                        if all(k in line for k in ['x0', 'y0', 'x1', 'y1']):
                            length = math.sqrt((line['x1'] - line['x0'])**2 + (line['y1'] - line['y0'])**2)
                            width = line.get('linewidth', 0.5)
                            ink_area += length * width
                    
                    if ink_area > 0:
                        return ink_area
        except Exception:
            pass
        
        # Phương pháp 2: Ước tính dựa trên font size
        if font_size > 0:
            # Ink area ước tính = font_size^1.5 * độ phức tạp ký tự
            char_complexity = 0.7  # Ký tự số thường đơn giản hơn chữ cái
            estimated_ink = (font_size ** 1.5) * char_complexity
            return estimated_ink
        
        # Phương pháp 3: Ước tính dựa trên kích thước bbox
        bbox_area = char_width * char_height
        ink_ratio = 0.5  # 50% bbox là ink
        return bbox_area * ink_ratio
        
    except Exception:
        # Phương pháp 4: Giá trị mặc định
        return 8.0

def is_number_in_alphanumeric(cluster, alphanumeric_strings, tolerance=3):
    """
    Kiểm tra xem cluster số có nằm trong chuỗi alphanumeric không
    """
    if not cluster or not alphanumeric_strings:
        return False
    
    try:
        cluster_bbox = {
            'x0': min(c['x0'] for c in cluster),
            'x1': max(c['x1'] for c in cluster),
            'top': min(c['top'] for c in cluster),
            'bottom': max(c['bottom'] for c in cluster)
        }
        
        for alpha_str in alphanumeric_strings:
            # Kiểm tra overlap với tolerance
            x_overlap = (cluster_bbox['x0'] < alpha_str['x1'] + tolerance and 
                        cluster_bbox['x1'] > alpha_str['x0'] - tolerance)
            y_overlap = (cluster_bbox['top'] < alpha_str['bottom'] + tolerance and 
                        cluster_bbox['bottom'] > alpha_str['top'] - tolerance)
            
            if x_overlap and y_overlap:
                return True
        
        return False
    except Exception:
        return False

def is_near_dimension_line(bbox, h_lines, v_lines, tolerance=15):
    """
    Kiểm tra xem số có gần đường kích thước không
    """
    try:
        center_x = (bbox['x0'] + bbox['x1']) / 2
        center_y = (bbox['top'] + bbox['bottom']) / 2
        
        # Kiểm tra đường ngang
        for h_line in h_lines:
            line_x_min = min(h_line['x0'], h_line['x1'])
            line_x_max = max(h_line['x0'], h_line['x1'])
            line_y = h_line['top']
            
            if (abs(line_y - center_y) < tolerance and 
                line_x_min < center_x < line_x_max):
                # Kiểm tra có tick marks không
                has_left_tick = any(abs(v['x0'] - line_x_min) < 3 for v in v_lines)
                has_right_tick = any(abs(v['x0'] - line_x_max) < 3 for v in v_lines)
                if has_left_tick and has_right_tick:
                    return True
        
        # Kiểm tra đường dọc
        for v_line in v_lines:
            line_y_min = min(v_line['top'], v_line['bottom'])
            line_y_max = max(v_line['top'], v_line['bottom'])
            line_x = v_line['x0']
            
            if (abs(line_x - center_x) < tolerance and 
                line_y_min < center_y < line_y_max):
                # Kiểm tra có tick marks không
                has_top_tick = any(abs(h['top'] - line_y_min) < 3 for h in h_lines)
                has_bottom_tick = any(abs(h['top'] - line_y_max) < 3 for h in h_lines)
                if has_top_tick and has_bottom_tick:
                    return True
        
        return False
    except Exception:
        return False

def calculate_confidence_score(number_info):
    """
    Tính điểm confidence với logic cải thiện
    """
    score = 30  # Điểm base cao hơn
    
    try:
        # Điểm từ dimension line (quan trọng nhất)
        if number_info.get('is_near_dimension_line', False):
            score += 50
        
        # Điểm từ ink area
        ink_area = number_info.get('ink_area', 0)
        if ink_area > 50:
            score += 25
        elif ink_area > 20:
            score += 20
        elif ink_area > 10:
            score += 15
        elif ink_area > 5:
            score += 10
        elif ink_area > 1:
            score += 5
        else:
            score -= 15  # Ink area quá thấp
        
        # Điểm từ font size
        font_size = number_info.get('font_size', 0)
        if font_size > 12:
            score += 15
        elif font_size > 8:
            score += 10
        elif font_size > 6:
            score += 5
        
        # Điểm từ orientation
        if number_info.get('orientation') == 'Horizontal':
            score += 5
        
        # Trừ điểm cho vị trí footer
        bbox = number_info.get('bbox', {})
        page_height = number_info.get('page_height', 800)
        if bbox.get('top', 0) > page_height * 0.9:
            score -= 30
        
        # Điểm từ giá trị số (số trong khoảng dimension hợp lý)
        value = number_info.get('value', 0)
        if 10 <= value <= 2000:  # Khoảng dimension thông thường
            score += 10
        elif 2000 < value <= 3000:
            score += 5
        elif value < 10:
            score -= 10
        
        return max(0, min(100, score))
    
    except Exception:
        return 30

def build_number_clusters(chars, orientation='Horizontal'):
    """
    Xây dựng clusters số từ chars
    """
    clusters = []
    if not chars:
        return clusters
    
    try:
        # Sắp xếp chars
        if orientation == 'Horizontal':
            sorted_chars = sorted(chars, key=lambda c: (round(c['top'], 1), c['x0']))
        else:
            sorted_chars = sorted(chars, key=lambda c: (round(c['x0'], 1), c['top']))
        
        current_cluster = []
        
        for char in sorted_chars:
            if char['text'].isdigit():
                if current_cluster:
                    last_char = current_cluster[-1]
                    
                    # Kiểm tra khoảng cách
                    if orientation == 'Horizontal':
                        distance = char['x0'] - last_char['x1']
                        line_diff = abs(char['top'] - last_char['top'])
                        max_distance = last_char.get('size', 8) * 0.6
                    else:
                        distance = char['top'] - last_char['bottom']
                        line_diff = abs(char['x0'] - last_char['x0'])
                        max_distance = last_char.get('size', 8) * 0.6
                    
                    if distance <= max_distance and line_diff <= 3:
                        current_cluster.append(char)
                    else:
                        if current_cluster:
                            clusters.append(current_cluster)
                        current_cluster = [char]
                else:
                    current_cluster = [char]
            else:
                if current_cluster:
                    clusters.append(current_cluster)
                    current_cluster = []
        
        if current_cluster:
            clusters.append(current_cluster)
        
        return clusters
    
    except Exception:
        return []

def extract_numbers_from_page(page_elements, h_lines, v_lines):
    """
    Trích xuất tất cả các số từ một trang
    """
    numbers_data = []
    
    try:
        # Xây dựng alphanumeric strings
        alphanumeric_strings = build_alphanumeric_strings(page_elements)
        
        # Tìm date zones để loại trừ
        date_zones = []
        try:
            if hasattr(page_elements, 'search'):
                date_zones = page_elements.search(r'\b\d{1,2}/\d{1,2}/\d{4}\b', regex=True) or []
        except:
            pass
        
        # Xử lý số nằm ngang
        h_chars = [c for c in page_elements['chars'] if c.get("upright", True)]
        h_clusters = build_number_clusters(h_chars, 'Horizontal')
        
        for cluster in h_clusters:
            result = process_number_cluster(
                cluster, page_elements, 'Horizontal', 
                h_lines, v_lines, alphanumeric_strings, date_zones
            )
            if result:
                numbers_data.append(result)
        
        # Xử lý số nằm dọc
        v_chars = [c for c in page_elements['chars'] if not c.get("upright", True)]
        if v_chars:
            # Nhóm theo cột
            cols = defaultdict(list)
            for char in v_chars:
                cols[round(char['x0'], 0)].append(char)
            
            for col_chars in cols.values():
                v_clusters = build_number_clusters(col_chars, 'Vertical')
                for cluster in v_clusters:
                    result = process_number_cluster(
                        cluster, page_elements, 'Vertical',
                        h_lines, v_lines, alphanumeric_strings, date_zones
                    )
                    if result:
                        numbers_data.append(result)
        
        return numbers_data
    
    except Exception as e:
        st.error(f"Lỗi khi trích xuất số: {e}")
        return []

def process_number_cluster(cluster, page_elements, orientation, h_lines, v_lines, 
                          alphanumeric_strings, date_zones):
    """
    Xử lý một cluster số
    """
    if not cluster:
        return None
    
    try:
        # Tạo chuỗi số
        number_str = "".join([c['text'] for c in cluster])
        if orientation == 'Vertical':
            number_str = number_str[::-1]
        
        # Kiểm tra số hợp lệ
        if not (number_str.isdigit() and 1 <= int(number_str) <= 3500):
            return None
        
        value = int(number_str)
        
        # Tạo bbox
        bbox = {
            'x0': min(c['x0'] for c in cluster),
            'x1': max(c['x1'] for c in cluster),
            'top': min(c['top'] for c in cluster),
            'bottom': max(c['bottom'] for c in cluster)
        }
        
        # Kiểm tra date zones
        if is_bbox_in_zones(bbox, date_zones):
            return None
        
        # Kiểm tra alphanumeric strings
        if is_number_in_alphanumeric(cluster, alphanumeric_strings):
            return None
        
        # Tính ink area
        # Tạo mock page object để tương thích
        class MockPage:
            def __init__(self, elements):
                self.width = elements['width']
                self.height = elements['height']
                self.rects = []
                self.lines = elements['lines']
            
            def crop(self, bbox):
                return self
        
        mock_page = MockPage(page_elements)
        ink_area = calculate_robust_ink_area(cluster, mock_page)
        
        # Loại bỏ ink area quá cao (graphics)
        if ink_area > 1000:
            return None
        
        # Kiểm tra dimension lines
        is_dim_line = is_near_dimension_line(bbox, h_lines, v_lines)
        
        # Lấy font size
        font_size = cluster[0].get('size', 0)
        
        # Tạo number info
        number_info = {
            'value': value,
            'bbox': bbox,
            'ink_area': ink_area,
            'orientation': orientation,
            'is_near_dimension_line': is_dim_line,
            'page_height': page_elements['height'],
            'font_size': font_size
        }
        
        confidence = calculate_confidence_score(number_info)
        
        return {
            'Number': value,
            'Ink Area': round(ink_area, 2),
            'Confidence (%)': confidence,
            'Font Size': font_size,
            'Orientation': orientation,
            'Near Dim Line': is_dim_line
        }
    
    except Exception:
        return None

def is_bbox_in_zones(bbox, zones):
    """
    Kiểm tra bbox có nằm trong zones không
    """
    try:
        for zone in zones:
            if (max(bbox['x0'], zone['x0']) < min(bbox['x1'], zone['x1']) and 
                max(bbox['top'], zone['top']) < min(bbox['bottom'], zone['bottom'])):
                return True
        return False
    except:
        return False

def extract_all_numbers_from_pdf(pdf_path):
    """
    Trích xuất tất cả số từ PDF
    """
    all_numbers = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                try:
                    page_elements = extract_page_elements(page)
                    h_lines, v_lines = find_dimension_lines(page_elements['lines'])
                    
                    page_numbers = extract_numbers_from_page(page_elements, h_lines, v_lines)
                    
                    # Thêm thông tin trang
                    for num_data in page_numbers:
                        num_data['Page'] = page_num + 1
                        all_numbers.append(num_data)
                        
                except Exception as e:
                    st.warning(f"Lỗi xử lý trang {page_num + 1}: {e}")
                    continue
        
        return all_numbers
    
    except Exception as e:
        st.error(f"Lỗi mở PDF: {e}")
        return []

# --- CÁC HÀM XỬ LÝ KÍCH THƯỚC ---

def assign_dimensions_from_numbers(numbers_df):
    """
    Gán kích thước từ danh sách số với logic cải thiện
    """
    dimensions = {'Length (mm)': '', 'Width (mm)': '', 'Height (mm)': ''}
    
    if numbers_df.empty:
        return dimensions
    
    try:
        # Nhóm theo ink area
        numbers_df = assign_ink_area_groups(numbers_df)
        
        # Tìm nhóm có ít nhất 3 số và confidence cao
        qualified_groups = numbers_df[
            (numbers_df['Group Size'] >= 3) & 
            (numbers_df['Confidence (%)'] >= 40)
        ]
        
        if not qualified_groups.empty:
            # Chọn nhóm có ink area cao nhất
            best_group = qualified_groups.loc[qualified_groups['Max Ink Area'].idxmax()]
            group_id = best_group['Ink Area Group']
            
            group_numbers = qualified_groups[qualified_groups['Ink Area Group'] == group_id]
            unique_numbers = sorted(group_numbers['Number'].unique())
            
            # Gán theo thứ tự: lớn nhất = Length, nhỏ nhất = Height, giữa = Width
            if len(unique_numbers) >= 3:
                dimensions['Length (mm)'] = unique_numbers[-1]  # Lớn nhất
                dimensions['Height (mm)'] = unique_numbers[0]   # Nhỏ nhất  
                dimensions['Width (mm)'] = unique_numbers[1]    # Giữa
            elif len(unique_numbers) == 2:
                dimensions['Length (mm)'] = unique_numbers[-1]
                dimensions['Width (mm)'] = unique_numbers[0]
        else:
            # Logic fallback: chọn 3 số có confidence cao nhất
            high_conf = numbers_df[numbers_df['Confidence (%)'] >= 50]
            if len(high_conf) >= 3:
                top_numbers = high_conf.nlargest(3, 'Confidence (%)')['Number'].tolist()
                top_numbers.sort()
                
                dimensions['Length (mm)'] = top_numbers[-1]
                dimensions['Height (mm)'] = top_numbers[0]
                if len(top_numbers) >= 2:
                    dimensions['Width (mm)'] = top_numbers[1] if len(top_numbers) == 3 else top_numbers[0]
    
    except Exception as e:
        st.error(f"Lỗi gán kích thước: {e}")
    
    return dimensions

def assign_ink_area_groups(df, tolerance=2.0):
    """
    Nhóm các số theo ink area tương tự
    """
    if df.empty:
        return df
    
    try:
        df = df.copy()
        unique_inks = sorted(df['Ink Area'].unique())
        
        groups = {}
        current_group = 1
        
        for ink in unique_inks:
            assigned = False
            for group_id, group_inks in groups.items():
                if any(abs(ink - existing_ink) <= tolerance for existing_ink in group_inks):
                    groups[group_id].append(ink)
                    assigned = True
                    break
            
            if not assigned:
                groups[current_group] = [ink]
                current_group += 1
        
        # Tạo mapping
        ink_to_group = {}
        for group_id, inks in groups.items():
            for ink in inks:
                ink_to_group[ink] = group_id
        
        df['Ink Area Group'] = df['Ink Area'].map(ink_to_group)
        df['Group Size'] = df.groupby('Ink Area Group')['Number'].transform('count')
        df['Max Ink Area'] = df.groupby('Ink Area Group')['Ink Area'].transform('max')
        
        return df
    
    except Exception:
        df['Ink Area Group'] = 1
        df['Group Size'] = len(df)
        df['Max Ink Area'] = df['Ink Area'].max() if not df.empty else 0
        return df

# --- CÁC HÀM XỬ LÝ KEYWORDS ---

def extract_laminate_info(pdf_path):
    """
    Trích xuất thông tin laminate
    """
    keywords = [
        "LAM/MASKING (IF APPLICABLE)",
        "GLUEABLE LAM/TC BLACK (IF APPLICABLE)", 
        "FLEX PAPER/PAPER",
        "GLUEABLE LAM",
        "RAW", 
        "LAM", 
        "GRAIN"
    ]
    
    found_keywords = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                for keyword in keywords:
                    if keyword in text.upper():
                        found_keywords.append(keyword)
                        break  # Chỉ lấy keyword đầu tiên tìm thấy
        
        # Xử lý kết quả
        if found_keywords:
            return found_keywords[0]  # Trả về keyword đầu tiên
        
        return ""
    
    except Exception:
        return ""

def extract_profile_info(pdf_path):
    """
    Trích xuất thông tin profile
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                match = re.search(r"PROFILE\s*:*\s*(\S+)", text, re.IGNORECASE)
                if match:
                    return match.group(1)
        return ""
    except:
        return ""

def extract_edgeband_foil_info(pdf_path):
    """
    Trích xuất thông tin edgeband và foil
    """
    result = {'Edgeband': '', 'Foil': ''}
    
    try:
        edgeband_patterns = {
            'L': ['EDGEBAND'],
            'S': ['DNABEGDE']
        }
        
        foil_patterns = {
            'L': ['FOIL'],  
            'S': ['LIOF']
        }
        
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                text_upper = text.upper()
                
                # Đếm edgeband
                edgeband_l = sum(text_upper.count(pattern) for pattern in edgeband_patterns['L'])
                edgeband_s = sum(text_upper.count(pattern) for pattern in edgeband_patterns['S'])
                
                # Đếm foil  
                foil_l = sum(text_upper.count(pattern) for pattern in foil_patterns['L'])
                foil_s = sum(text_upper.count(pattern) for pattern in foil_patterns['S'])
        
        # Giới hạn tối đa 2
        edgeband_l = min(edgeband_l, 2)
        edgeband_s = min(edgeband_s, 2)
        foil_l = min(foil_l, 2)
        foil_s = min(foil_s, 2)
        
        # Tạo chuỗi kết quả
        if edgeband_l > 0:
            result['Edgeband'] += f"{edgeband_l}L"
        if edgeband_s > 0:
            result['Edgeband'] += f"{edgeband_s}S"
            
        if foil_l > 0:
            result['Foil'] += f"{foil_l}L"
        if foil_s > 0:
            result['Foil'] += f"{foil_s}S"
    
    except Exception:
        pass
    
    return result

# --- HÀM XỬ LÝ PDF CHÍNH ---

def process_single_pdf(pdf_path, filename):
    """
    Xử lý một file PDF
    """
    try:
        # Trích xuất numbers
        numbers_data = extract_all_numbers_from_pdf(pdf_path)
        
        # Tạo DataFrame
        if numbers_data:
            numbers_df = pd.DataFrame(numbers_data)
            dimensions = assign_dimensions_from_numbers(numbers_df)
        else:
            dimensions = {'Length (mm)': '', 'Width (mm)': '', 'Height (mm)': ''}
        
        # Trích xuất các thông tin khác
        laminate = extract_laminate_info(pdf_path)
        profile = extract_profile_info(pdf_path)
        edgeband_foil = extract_edgeband_foil_info(pdf_path)
        
        # Kiểm tra status
        status = 'Done' if all(dimensions.values()) else 'Recheck'
        
        result = {
            'Drawing #': os.path.splitext(filename)[0],
            'Length (mm)': dimensions['Length (mm)'],
            'Width (mm)': dimensions['Width (mm)'],
            'Height (mm)': dimensions['Height (mm)'],
            'Laminate': laminate,
            'Edgeband': edgeband_foil['Edgeband'],
            'Foil': edgeband_foil['Foil'],
            'Profile': profile,
            'Status': status
        }
        
        return result, numbers_data
    
    except Exception as e:
        error_result = {
            'Drawing #': os.path.splitext(filename)[0],
            'Length (mm)': 'ERROR',
            'Width (mm)': 'ERROR', 
            'Height (mm)': 'ERROR',
            'Laminate': 'ERROR',
            'Edgeband': 'ERROR',
            'Foil': 'ERROR',
            'Profile': 'ERROR',
            'Status': 'ERROR'
        }
        return error_result, []

# --- UTILITY FUNCTIONS ---

def save_uploaded_file(uploaded_file):
    """
    Lưu file upload vào temporary file
    """
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            return tmp_file.name
    except Exception as e:
        st.error(f"Lỗi lưu file: {e}")
        return None

def to_excel(df):
    """
    Chuyển DataFrame sang Excel
    """
    output = io.BytesIO()
    try:
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Results')
        return output.getvalue()
    except ImportError:
        try:
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Results')
            return output.getvalue()
        except ImportError:
            return None

# --- MAIN STREAMLIT APP ---

def main():
    st.title("📄 PDF Data Extractor - Phiên bản cải tiến")
    st.markdown("Trích xuất kích thước và thông tin từ bản vẽ kỹ thuật PDF")
    
    # Sidebar cho debug
    with st.sidebar:
        st.header("🔧 Debug Options")
        show_debug = st.checkbox("Hiển thị debug info")
        show_numbers_detail = st.checkbox("Hiển thị chi tiết số")
    
    # File uploader
    uploaded_files = st.file_uploader(
        "Chọn file PDF",
        type="pdf",
        accept_multiple_files=True,
        help="Có thể chọn nhiều file cùng lúc"
    )
    
    if uploaded_files:
        total_files = len(uploaded_files)
        st.info(f"📁 Đã chọn {total_files} file(s)")
        
        # Process button
        if st.button("🚀 Bắt đầu xử lý", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            all_results = []
            all_numbers_data = []
            
            for i, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"Đang xử lý {uploaded_file.name}...")
                
                temp_path = save_uploaded_file(uploaded_file)
                if temp_path:
                    try:
                        result, numbers_data = process_single_pdf(temp_path, uploaded_file.name)
                        all_results.append(result)
                        
                        if show_numbers_detail and numbers_data:
                            all_numbers_data.extend([
                                {**num_data, 'File': uploaded_file.name} 
                                for num_data in numbers_data
                            ])
                        
                    except Exception as e:
                        st.error(f"Lỗi xử lý {uploaded_file.name}: {e}")
                    finally:
                        if os.path.exists(temp_path):
                            os.unlink(temp_path)
                
                progress_bar.progress((i + 1) / total_files)
            
            status_text.text("✅ Hoàn thành!")
            
            # Hiển thị kết quả
            if all_results:
                st.success(f"✅ Đã xử lý thành công {len(all_results)} file(s)")
                
                # Kết quả chính
                st.subheader("📊 Kết quả trích xuất")
                results_df = pd.DataFrame(all_results)
                st.dataframe(results_df, use_container_width=True, hide_index=True)
                
                # Thống kê
                col1, col2, col3 = st.columns(3)
                with col1:
                    done_count = sum(1 for r in all_results if r['Status'] == 'Done')
                    st.metric("✅ Hoàn thành", done_count)
                with col2:
                    recheck_count = sum(1 for r in all_results if r['Status'] == 'Recheck')
                    st.metric("⚠️ Cần kiểm tra", recheck_count)
                with col3:
                    error_count = sum(1 for r in all_results if r['Status'] == 'ERROR')
                    st.metric("❌ Lỗi", error_count)
                
                # Download button
                excel_data = to_excel(results_df)
                if excel_data:
                    st.download_button(
                        label="📥 Tải xuống Excel",
                        data=excel_data,
                        file_name="pdf_extraction_results.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                
                # Debug info
                if show_debug and all_numbers_data:
                    st.subheader("🔍 Chi tiết số được phát hiện")
                    numbers_df = pd.DataFrame(all_numbers_data)
                    st.dataframe(numbers_df, use_container_width=True, hide_index=True)
    
    else:
        st.info("👆 Vui lòng chọn file PDF để bắt đầu")
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666; font-size: 0.9em;'>
        🛠️ PDF Data Extractor v2.0 | Được tối ưu hóa cho bản vẽ kỹ thuật
        </div>
        """, 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()

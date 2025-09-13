import streamlit as st
import pdfplumber
import re
import pandas as pd
from collections import defaultdict
import os
import tempfile
import io
import math
import time
import traceback
from contextlib import contextmanager
import gc

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="PDF Data Extractor",
    page_icon="📄",
    layout="wide"
)

# --- CONTEXT MANAGER ĐỂ XỬ LÝ FILE AN TOÀN ---
@contextmanager
def safe_pdf_processing(pdf_path, timeout=30):
    """Context manager để xử lý PDF an toàn với timeout"""
    start_time = time.time()
    pdf_obj = None
    try:
        pdf_obj = pdfplumber.open(pdf_path)
        yield pdf_obj
    except Exception as e:
        st.error(f"Lỗi khi mở PDF: {str(e)}")
        raise e
    finally:
        # Đảm bảo đóng file
        if pdf_obj:
            try:
                pdf_obj.close()
            except:
                pass
        # Kiểm tra timeout
        if time.time() - start_time > timeout:
            st.warning("⚠️ File xử lý quá lâu, có thể bị timeout")
        # Dọn dẹp memory
        gc.collect()

# --- HÀM XỬ LÝ FILE TEMP AN TOÀN ---
def save_uploaded_file_safe(uploaded_file):
    """Lưu file upload một cách an toàn"""
    temp_path = None
    try:
        # Tạo file tạm thời
        temp_fd, temp_path = tempfile.mkstemp(suffix='.pdf', prefix='pdf_extract_')
        
        # Ghi dữ liệu vào file
        with os.fdopen(temp_fd, 'wb') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_file.flush()
            os.fsync(tmp_file.fileno())  # Đảm bảo dữ liệu được ghi vào disk
        
        return temp_path
    except Exception as e:
        st.error(f"Lỗi khi lưu file {uploaded_file.name}: {str(e)}")
        # Dọn dẹp nếu có lỗi
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass
        return None

def cleanup_temp_file(file_path):
    """Dọn dẹp file tạm thời một cách an toàn"""
    if file_path and os.path.exists(file_path):
        try:
            os.unlink(file_path)
            return True
        except Exception as e:
            st.warning(f"Không thể xóa file tạm: {str(e)}")
            return False
    return True

# --- CÁC HÀM PHỤ TRỢ (LOGIC XỬ LÝ) ---
def find_dimension_lines(lines, tolerance=2):
    """Tìm các đường dimension với xử lý lỗi"""
    try:
        horizontal_lines = [line for line in lines if abs(line['y0'] - line['y1']) <= tolerance]
        vertical_lines = [line for line in lines if abs(line['x0'] - line['x1']) <= tolerance]
        return horizontal_lines, vertical_lines
    except Exception:
        return [], []

def is_near_dimension_line(number_bbox, h_lines, v_lines, tolerance=15):
    """Kiểm tra có gần đường dimension không với xử lý lỗi"""
    try:
        num_x_center = (number_bbox['x0'] + number_bbox['x1']) / 2
        num_y_center = (number_bbox['top'] + number_bbox['bottom']) / 2
        
        for h_line in h_lines:
            line_x_min, line_x_max = min(h_line['x0'], h_line['x1']), max(h_line['x0'], h_line['x1'])
            if (abs(h_line['top'] - num_y_center) < tolerance) and (line_x_min < num_x_center < line_x_max):
                left_tick = any(abs(v['x0'] - line_x_min) < 2 for v in v_lines)
                right_tick = any(abs(v['x0'] - line_x_max) < 2 for v in v_lines)
                if left_tick and right_tick: return True
                
        for v_line in v_lines:
            line_y_min, line_y_max = min(v_line['top'], v_line['bottom']), max(v_line['top'], v_line['bottom'])
            if (abs(v_line['x0'] - num_x_center) < tolerance) and (line_y_min < num_y_center < line_y_max):
                top_tick = any(abs(h['top'] - line_y_min) < 2 for h in h_lines)
                bottom_tick = any(abs(h['top'] - line_y_max) < 2 for h in h_lines)
                if top_tick and bottom_tick: return True
    except Exception:
        pass
    return False

def is_bbox_inside_zones(bbox, zones):
    """Kiểm tra bbox có trong zones không"""
    try:
        for zone in zones:
            if (max(bbox['x0'], zone['x0']) < min(bbox['x1'], zone['x1']) and 
                max(bbox['top'], zone['top']) < min(bbox['bottom'], zone['bottom'])):
                return True
    except Exception:
        pass
    return False

def get_ink_area_of_first_char(cluster, page):
    """Tính ink area với xử lý lỗi"""
    try:
        if not cluster: return 0.0
        first_char = cluster[0]
        char_bbox = (first_char['x0'], first_char['top'], first_char['x1'], first_char['bottom'])
        cropped_char_page = page.crop(char_bbox)
        ink_area = 0.0
        
        for rect in cropped_char_page.rects: 
            ink_area += rect['width'] * rect['height']
        for line in cropped_char_page.lines: 
            ink_area += math.sqrt((line['x1'] - line['x0'])**2 + (line['y1'] - line['y0'])**2) * line.get('linewidth', 1)
        return ink_area
    except Exception:
        return 0.0

def calculate_confidence(number_info):
    """Tính confidence score"""
    try:
        score = 20
        if number_info['is_near_dimension_line']: score += 50
        if number_info['ink_area'] > 15: score += 25
        elif number_info['ink_area'] > 8: score += 15
        if number_info['bbox']['top'] > number_info['page_height'] * 0.85: score -= 40
        if number_info['orientation'] == 'Horizontal': score += 5
        else: score -= 5
        return max(0, min(100, score))
    except Exception:
        return 0

def process_cluster_for_new_logic(cluster, page, orientation, h_lines, v_lines, date_zones):
    """Xử lý cluster với xử lý lỗi toàn diện"""
    try:
        if not cluster: return None
        number_str = "".join([c['text'] for c in cluster])
        if orientation == 'Vertical': number_str = number_str[::-1]
        
        if number_str.isdigit() and int(number_str) < 3500:
            value = int(number_str)
            bbox = {
                'x0': min(c['x0'] for c in cluster), 
                'top': min(c['top'] for c in cluster), 
                'x1': max(c['x1'] for c in cluster), 
                'bottom': max(c['bottom'] for c in cluster)
            }
            
            if is_bbox_inside_zones(bbox, date_zones): return None
            ink_area = get_ink_area_of_first_char(cluster, page)
            if ink_area > 200: return None
            
            is_dim_line = is_near_dimension_line(bbox, h_lines, v_lines)
            number_info = {
                'value': value, 'bbox': bbox, 'ink_area': ink_area, 
                'orientation': orientation, 'is_near_dimension_line': is_dim_line, 
                'page_height': page.height
            }
            confidence = calculate_confidence(number_info)
            return {'Number': value, 'Ink Area': round(ink_area, 2), 'Confidence (%)': confidence}
    except Exception as e:
        # Log lỗi nhưng không crash
        pass
    return None

def extract_all_numbers_safe(pdf_path):
    """Trích xuất số với xử lý lỗi và timeout"""
    all_numbers_data = []
    
    try:
        with safe_pdf_processing(pdf_path, timeout=60) as pdf:
            for page_num, page in enumerate(pdf.pages):
                try:
                    # Kiểm tra timeout cho từng page
                    start_page_time = time.time()
                    
                    lines = page.lines if hasattr(page, 'lines') else []
                    h_lines, v_lines = find_dimension_lines(lines)
                    
                    # Tìm date zones với xử lý lỗi
                    try:
                        date_zones = page.search(r'\b\d{1,2}/\d{1,2}/\d{4}\b', regex=True) or []
                    except:
                        date_zones = []
                    
                    # Xử lý horizontal chars
                    try:
                        h_chars = sorted([c for c in page.chars if c.get("upright", True)], 
                                       key=lambda c: (round(c["top"], 1), c["x0"]))
                        current_cluster, last_char = [], None
                        
                        for char in h_chars:
                            # Kiểm tra timeout
                            if time.time() - start_page_time > 30:
                                st.warning(f"⚠️ Page {page_num + 1} xử lý quá lâu, bỏ qua")
                                break
                                
                            if char['text'].isdigit():
                                if (current_cluster and last_char and 
                                    (char['x0'] - last_char['x1'] > char.get('size', 8) * 0.6 or 
                                     abs(char['top'] - last_char['top']) > 2)):
                                    result = process_cluster_for_new_logic(current_cluster, page, 'Horizontal', h_lines, v_lines, date_zones)
                                    if result: all_numbers_data.append(result)
                                    current_cluster = [char]
                                else: 
                                    current_cluster.append(char)
                            else:
                                if current_cluster:
                                    result = process_cluster_for_new_logic(current_cluster, page, 'Horizontal', h_lines, v_lines, date_zones)
                                    if result: all_numbers_data.append(result)
                                current_cluster = []
                            last_char = char
                        
                        if current_cluster:
                            result = process_cluster_for_new_logic(current_cluster, page, 'Horizontal', h_lines, v_lines, date_zones)
                            if result: all_numbers_data.append(result)
                    except Exception as e:
                        st.warning(f"Lỗi xử lý horizontal chars ở page {page_num + 1}: {str(e)}")
                    
                    # Xử lý vertical chars
                    try:
                        v_chars_by_col = defaultdict(list)
                        for char in [c for c in page.chars if not c.get("upright", True)]: 
                            v_chars_by_col[round(char['x0'], 0)].append(char)
                        
                        for col in v_chars_by_col.values():
                            if time.time() - start_page_time > 30:
                                break
                                
                            col.sort(key=lambda c: c['top'])
                            current_cluster, last_char = [], None
                            
                            for char in col:
                                if char['text'].isdigit():
                                    if (current_cluster and last_char and 
                                        (char['top'] - last_char['bottom'] > char.get('size', 8) * 0.6)):
                                        result = process_cluster_for_new_logic(current_cluster, page, 'Vertical', h_lines, v_lines, date_zones)
                                        if result: all_numbers_data.append(result)
                                        current_cluster = [char]
                                    else: 
                                        current_cluster.append(char)
                                else:
                                    if current_cluster:
                                        result = process_cluster_for_new_logic(current_cluster, page, 'Vertical', h_lines, v_lines, date_zones)
                                        if result: all_numbers_data.append(result)
                                    current_cluster = []
                                last_char = char
                            
                            if current_cluster:
                                result = process_cluster_for_new_logic(current_cluster, page, 'Vertical', h_lines, v_lines, date_zones)
                                if result: all_numbers_data.append(result)
                    except Exception as e:
                        st.warning(f"Lỗi xử lý vertical chars ở page {page_num + 1}: {str(e)}")
                        
                except Exception as e:
                    st.warning(f"Lỗi xử lý page {page_num + 1}: {str(e)}")
                    continue
                    
    except Exception as e:
        st.error(f"Lỗi nghiêm trọng khi xử lý PDF: {str(e)}")
        
    return all_numbers_data

def assign_ink_groups(df, tolerance=1.0):
    """Gán ink groups với xử lý lỗi"""
    try:
        if df.empty or 'Ink Area' not in df.columns:
            df['Ink Area Group'] = 0
            return df
        unique_inks = sorted(df['Ink Area'].unique())
        if not unique_inks:
            df['Ink Area Group'] = 0
            return df
        group_mapping, current_group_id = {}, 1
        group_mapping[unique_inks[0]] = current_group_id
        last_val_in_group = unique_inks[0]
        for ink in unique_inks[1:]:
            if ink - last_val_in_group <= tolerance:
                group_mapping[ink] = current_group_id
            else:
                current_group_id += 1
                group_mapping[ink] = current_group_id
            last_val_in_group = ink
        df['Ink Area Group'] = df['Ink Area'].map(group_mapping)
        return df
    except Exception:
        df['Ink Area Group'] = 0
        return df

def find_laminate_keywords_safe(pdf_path):
    """Tìm laminate keywords với xử lý lỗi"""
    target_keywords = ["LAM/MASKING (IF APPLICABLE)","GLUEABLE LAM/TC BLACK (IF APPLICABLE)",
                      "FLEX PAPER/PAPER", "GLUEABLE LAM", "RAW", "LAM", "GRAIN"]
    found_pairs = []
    
    try:
        with safe_pdf_processing(pdf_path, timeout=30) as pdf:
            for page in pdf.pages:
                try:
                    chars = page.chars
                    if not chars: continue
                    chars = sorted(chars, key=lambda c: (round(c["top"], 1), c["x0"]))
                    full_text = "".join(c["text"] for c in chars)
                    
                    for keyword in target_keywords:
                        try:
                            for pos in [m.start() for m in re.finditer(re.escape(keyword), full_text)]:
                                keyword_chars = chars[pos:pos + len(keyword)]
                                if not keyword_chars: continue
                                keyword_y = sum(c["top"] for c in keyword_chars) / len(keyword_chars)
                                keyword_x_center = sum(c["x0"] for c in keyword_chars) / len(keyword_chars)
                                below_word = find_word_below_safe(chars, keyword_y, keyword_x_center, target_keywords)
                                if below_word: found_pairs.append(f"{keyword}/{below_word}")
                                else: found_pairs.append(keyword)
                        except Exception:
                            continue
                except Exception:
                    continue
    except Exception:
        pass
        
    return found_pairs

def find_word_below_safe(chars, keyword_y, keyword_x_center, target_keywords, y_tolerance=50, x_tolerance=100):
    """Tìm word below với xử lý lỗi"""
    try:
        chars_below = [c for c in chars if c["top"] > keyword_y + 5]
        if not chars_below: return None
        chars_below.sort(key=lambda c: c["top"])
        lines = []
        current_line, current_y = [], None
        for char in chars_below:
            if current_y is None or abs(char["top"] - current_y) <= 3:
                current_line.append(char)
                current_y = char["top"]
            else:
                if current_line: lines.append(current_line)
                current_line, current_y = [char], char["top"]
        if current_line: lines.append(current_line)
        for line_chars in lines:
            line_chars.sort(key=lambda c: c["x0"])
            line_text = "".join(c["text"] for c in line_chars).strip()
            for keyword in target_keywords:
                if keyword in line_text:
                    line_x_center = sum(c["x0"] for c in line_chars) / len(line_chars)
                    if abs(line_x_center - keyword_x_center) <= x_tolerance: return keyword
    except Exception:
        pass
    return None

def process_laminate_result(laminate_string):
    """Xử lý laminate result với xử lý lỗi"""
    try:
        target_keywords = ["FLEX PAPER/PAPER", "GLUEABLE LAM", "LAM", "RAW", "GRAIN"]
        if not laminate_string or laminate_string.strip() == "": return ""
        parts = [part.strip() for part in laminate_string.split(" / ")]
        if not parts: return ""
        clusters = [part for part in parts if "/" in part]
        if not clusters:
            for keyword in target_keywords:
                if keyword in parts: return keyword
            return parts[-1] if parts else ""
        best_cluster, best_priority = "", float('inf')
        for cluster in clusters:
            cluster_keywords = cluster.split("/")
            cluster_priority = float('inf')
            for keyword in cluster_keywords:
                keyword = keyword.strip()
                if keyword in target_keywords:
                    priority = target_keywords.index(keyword)
                    if priority < cluster_priority: cluster_priority = priority
            if cluster_priority < best_priority: best_priority, best_cluster = cluster_priority, cluster
        if not best_cluster: best_cluster = clusters[-1]
        return best_cluster
    except Exception:
        return ""

def find_profile_a_safe(pdf_path):
    """Tìm profile với xử lý lỗi"""
    try:
        with safe_pdf_processing(pdf_path, timeout=15) as pdf:
            for page in pdf.pages:
                try:
                    text = page.extract_text()
                    if text:
                        match = re.search(r"PROFILE\s*:*\s*(\S+)", text, re.IGNORECASE)
                        if match: return match.group(1)
                except Exception:
                    continue
    except Exception:
        pass
    return ""

def extract_edgeband_and_foil_keywords_safe(pdf_path):
    """Trích xuất edgeband và foil với xử lý lỗi"""
    try:
        edgeband_L_keywords = {"EDGEBAND"}
        edgeband_S_keywords = {"DNABEGDE"}
        foil_L_keywords = {"FOIL"}
        foil_S_keywords = {"LIOF"}

        edgeband_L_count, edgeband_S_count = 0, 0
        foil_L_count, foil_S_count = 0, 0

        with safe_pdf_processing(pdf_path, timeout=20) as pdf:
            for page in pdf.pages:
                try:
                    words = page.extract_words(x_tolerance=2)
                    if not words: continue
                    
                    page_words = [w["text"].upper() for w in words]

                    edgeband_L_count += sum(1 for t in page_words if t in edgeband_L_keywords)
                    edgeband_S_count += sum(1 for t in page_words if t in edgeband_S_keywords)
                    foil_L_count += sum(1 for t in page_words if t in foil_L_keywords)
                    foil_S_count += sum(1 for t in page_words if t in foil_S_keywords)
                except Exception:
                    continue
                
        # Áp dụng giới hạn
        edgeband_L_count, edgeband_S_count = min(edgeband_L_count, 2), min(edgeband_S_count, 2)
        foil_L_count, foil_S_count = min(foil_L_count, 2), min(foil_S_count, 2)

        # Tạo chuỗi kết quả cho Edgeband
        edgeband_result = ""
        if edgeband_L_count > 0: edgeband_result += f"{edgeband_L_count}L"
        if edgeband_S_count > 0: edgeband_result += f"{edgeband_S_count}S"

        # Tạo chuỗi kết quả cho Foil
        foil_result = ""
        if foil_L_count > 0: foil_result += f"{foil_L_count}L"
        if foil_S_count > 0: foil_result += f"{foil_S_count}S"

        return {'Edgeband': edgeband_result, 'Foil': foil_result}
    except Exception:
        return {'Edgeband': '', 'Foil': ''}

def check_dimensions_status(length, width, height):
    """Kiểm tra status dimensions"""
    try:
        if (length and str(length) != '' and str(length) != 'ERROR' and 
            width and str(width) != '' and str(width) != 'ERROR' and 
            height and str(height) != '' and str(height) != 'ERROR'):
            return 'Done'
    except Exception:
        pass
    return 'Recheck'

def process_single_pdf_safe(pdf_path, original_filename, timeout=120):
    """Xử lý một file PDF với timeout và xử lý lỗi toàn diện"""
    start_time = time.time()
    
    try:
        # Kiểm tra file tồn tại
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"File không tồn tại: {pdf_path}")
        
        # Kiểm tra kích thước file
        file_size = os.path.getsize(pdf_path)
        if file_size > 50 * 1024 * 1024:  # 50MB
            st.warning(f"⚠️ File {original_filename} lớn ({file_size//1024//1024}MB), có thể xử lý chậm")
        
        # Trích xuất numbers
        numbers = extract_all_numbers_safe(pdf_path)
        
        # Kiểm tra timeout
        if time.time() - start_time > timeout:
            raise TimeoutError(f"Xử lý file quá lâu (>{timeout}s)")
        
        dim_map = {}
        if numbers:
            try:
                full_df = pd.DataFrame(numbers)
                full_df = assign_ink_groups(full_df, tolerance=1.0)
                full_df['Ink Area Group Count'] = full_df.groupby('Ink Area Group')['Ink Area'].transform('count')
                
                qualified_groups_df = full_df[full_df['Ink Area Group Count'] >= 3].copy()
                
                if not qualified_groups_df.empty:
                    qualified_groups_df['Max Ink Area'] = qualified_groups_df.groupby('Ink Area Group')['Ink Area'].transform('max')
                    sorted_qualified_groups = qualified_groups_df.sort_values(by='Max Ink Area', ascending=False)
                    top_ink_area_group_id = sorted_qualified_groups.iloc[0]['Ink Area Group']
                    top_group_df = qualified_groups_df[qualified_groups_df['Ink Area Group'] == top_ink_area_group_id]
                    unique_numbers_in_group = sorted(top_group_df['Number'].unique())
                    
                    if len(unique_numbers_in_group) >= 1: dim_map[unique_numbers_in_group[-1]] = 'Length (mm)'
                    if len(unique_numbers_in_group) >= 2: dim_map[unique_numbers_in_group[0]] = 'Height (mm)'
                    if len(unique_numbers_in_group) >= 3: dim_map[unique_numbers_in_group[1]] = 'Width (mm)'
                else:
                    high_confidence_dims = full_df[full_df['Confidence (%)'] > 50]
                    if not high_confidence_dims.empty:
                        top_dims = high_confidence_dims.drop_duplicates(subset=['Number']).head(3)
                        sorted_dims = top_dims.sort_values(by='Number', ascending=False)['Number'].tolist()
                        if len(sorted_dims) >= 1: dim_map[sorted_dims[0]] = 'Length (mm)'
                        if len(sorted_dims) >= 3: dim_map[sorted_dims[1]] = 'Width (mm)'; dim_map[sorted_dims[2]] = 'Height (mm)'
                        elif len(sorted_dims) == 2: dim_map[sorted_dims[1]] = 'Width (mm)'
            except Exception as e:
                st.warning(f"Lỗi xử lý dimensions cho {original_filename}: {str(e)}")

        # Trích xuất các thông tin khác
        try:
            laminate_pairs = find_laminate_keywords_safe(pdf_path)
            laminate_raw_result = " / ".join(laminate_pairs) if laminate_pairs else ""
            laminate_result = process_laminate_result(laminate_raw_result) if laminate_pairs else ""
        except Exception:
            laminate_result = ""
            
        try:
            profile_a_result = find_profile_a_safe(pdf_path)
        except Exception:
            profile_a_result = ""
            
        try:
            edgeband_foil_results = extract_edgeband_and_foil_keywords_safe(pdf_path)
        except Exception:
            edgeband_foil_results = {'Edgeband': '', 'Foil': ''}

        final_result = {
            'Drawing #': os.path.splitext(original_filename)[0],
            'Length (mm)': next((k for k, v in dim_map.items() if v == 'Length (mm)'), ''),
            'Width (mm)': next((k for k, v in dim_map.items() if v == 'Width (mm)'), ''),
            'Height (mm)': next((k for k, v in dim_map.items() if v == 'Height (mm)'), ''),
            'Laminate': laminate_result,
            'Edgeband': edgeband_foil_results['Edgeband'],
            'Foil': edgeband_foil_results['Foil'],
            'Profile': profile_a_result
        }
        
        final_result['Status'] = check_dimensions_status(
            final_result['Length (mm)'], 
            final_result['Width (mm)'], 
            final_result['Height (mm)']
        )
        
        # Log thời gian xử lý
        processing_time = time.time() - start_time
        if processing_time > 30:
            st.info(f"⏱️ File {original_filename} xử lý trong {processing_time:.1f}s")
        
        return final_result
        
    except TimeoutError as e:
        st.error(f"⏰ Timeout: {str(e)}")
        return create_error_result(original_filename, "TIMEOUT")
    except Exception as e:
        st.error(f"❌ Lỗi xử lý {original_filename}: {str(e)}")
        # Log chi tiết lỗi để debug
        error_details = traceback.format_exc()
        st.expander("Chi tiết lỗi").code(error_details)
        return create_error_result(original_filename, "ERROR")

def create_error_result(filename, error_type="ERROR"):
    """Tạo kết quả lỗi chuẩn"""
    return {
        'Drawing #': os.path.splitext(filename)[0],
        'Length (mm)': error_type, 'Width (mm)': error_type, 'Height (mm)': error_type,
        'Laminate': error_type, 'Edgeband': error_type, 'Foil': error_type,
        'Profile': error_type, 'Status': error_type
    }

def to_excel(df):
    """Export to Excel với xử lý lỗi"""
    output = io.BytesIO()
    try:
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer: 
            df.to_excel(writer, index=False, sheet_name='PDF_Extraction_Results')
    except ImportError:
        try:
            with pd.ExcelWriter(output, engine='openpyxl') as writer: 
                df.to_excel(writer, index=False, sheet_name='PDF_Extraction_Results')
        except ImportError: 
            return None
    except Exception:
        return None
    return output.getvalue()

# ===== GIAO DIỆN STREAMLIT AN TOÀN =====
def main():
    st.title("📄 Trình trích xuất dữ liệu PDF (Safe Mode)")
    st.write("Tự động nhận diện kích thước và thông tin từ bản vẽ kỹ thuật với xử lý lỗi toàn diện.")

    uploaded_files = st.file_uploader(
        "Kéo và thả file PDF vào đây hoặc nhấn để chọn",
        type="pdf",
        accept_multiple_files=True,
        label_visibility="collapsed"
    )
    
    if uploaded_files:
        all_final_results = []
        total_files = len(uploaded_files)
        
        # Hiển thị thông tin tổng quan
        st.info(f"📊 Sẽ xử lý {total_files} file PDF")
        
        # Tạo container cho progress và status
        progress_container = st.container()
        
        with progress_container:
            progress_bar = st.progress(0)
            status_text = st.empty()
            file_status = st.empty()
            time_info = st.empty()
        
        start_total_time = time.time()
        
        # Xử lý từng file
        for i, uploaded_file in enumerate(uploaded_files):
            current_file = i + 1
            file_start_time = time.time()
            
            # Cập nhật trạng thái
            status_text.text(f"⏳ Đang xử lý file {current_file}/{total_files}")
            file_status.info(f"📄 **{uploaded_file.name}** (Kích thước: {uploaded_file.size//1024}KB)")
            
            temp_path = None
            try:
                # Lưu file tạm thời
                temp_path = save_uploaded_file_safe(uploaded_file)
                if not temp_path:
                    raise Exception("Không thể lưu file tạm thời")
                
                # Xử lý file
                final_result = process_single_pdf_safe(temp_path, uploaded_file.name, timeout=120)
                all_final_results.append(final_result)
                
                # Tính thời gian xử lý
                file_time = time.time() - file_start_time
                
                # Hiển thị kết quả
                if final_result['Status'] == 'Done':
                    file_status.success(f"✅ **{uploaded_file.name}** - Thành công ({file_time:.1f}s)")
                elif final_result['Status'] == 'Recheck':
                    file_status.warning(f"⚠️ **{uploaded_file.name}** - Cần kiểm tra lại ({file_time:.1f}s)")
                else:
                    file_status.error(f"❌ **{uploaded_file.name}** - Lỗi ({file_time:.1f}s)")
                    
            except Exception as e:
                error_result = create_error_result(uploaded_file.name, "CRITICAL_ERROR")
                all_final_results.append(error_result)
                file_status.error(f"💥 **{uploaded_file.name}** - Lỗi nghiêm trọng: {str(e)}")
                
            finally:
                # Dọn dẹp file tạm thời
                if temp_path:
                    cleanup_success = cleanup_temp_file(temp_path)
                    if not cleanup_success:
                        st.warning(f"⚠️ Không thể dọn dẹp file tạm cho {uploaded_file.name}")
                
                # Force garbage collection
                gc.collect()
            
            # Cập nhật progress bar
            progress_percentage = current_file / total_files
            progress_bar.progress(progress_percentage)
            
            # Hiển thị thời gian ước tính
            elapsed_time = time.time() - start_total_time
            if current_file > 1:
                avg_time_per_file = elapsed_time / current_file
                remaining_files = total_files - current_file
                eta = remaining_files * avg_time_per_file
                time_info.text(f"⏱️ Đã qua: {elapsed_time:.0f}s | Ước tính còn lại: {eta:.0f}s")
        
        # Hoàn thành xử lý
        total_time = time.time() - start_total_time
        progress_bar.progress(1.0)
        status_text.success(f"✅ Hoàn thành xử lý {total_files} file trong {total_time:.1f}s!")
        file_status.empty()
        time_info.empty()
        
        if all_final_results:
            st.markdown("---")
            
            # Hiển thị thống kê tổng quan
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                done_count = sum(1 for result in all_final_results if result['Status'] == 'Done')
                st.metric("✅ Thành công", done_count)
            with col2:
                recheck_count = sum(1 for result in all_final_results if result['Status'] == 'Recheck')
                st.metric("⚠️ Cần kiểm tra", recheck_count)
            with col3:
                error_count = sum(1 for result in all_final_results if 'ERROR' in str(result['Status']))
                st.metric("❌ Lỗi", error_count)
            with col4:
                success_rate = (done_count / total_files * 100) if total_files > 0 else 0
                st.metric("📈 Tỷ lệ thành công", f"{success_rate:.1f}%")
            
            st.markdown("---")
            st.subheader("📊 Kết quả trích xuất chi tiết")
            
            final_results_df = pd.DataFrame(all_final_results)
            
            # Tô màu theo status
            def highlight_status(val):
                if val == 'Done':
                    return 'background-color: #d4edda; color: #155724'
                elif val == 'Recheck':
                    return 'background-color: #fff3cd; color: #856404'
                elif 'ERROR' in str(val) or 'TIMEOUT' in str(val):
                    return 'background-color: #f8d7da; color: #721c24'
                return ''
            
            styled_df = final_results_df.style.applymap(highlight_status, subset=['Status'])
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            
            # Nút download
            col1, col2 = st.columns(2)
            with col1:
                excel_data = to_excel(final_results_df)
                if excel_data:
                    st.download_button(
                        label="📥 Tải về file Excel",
                        data=excel_data,
                        file_name=f"pdf_extraction_results_{total_files}_files_{int(time.time())}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.button("📊 Excel (Không khả dụng)", disabled=True, 
                             help="Cần cài đặt thư viện xlsxwriter hoặc openpyxl")
            
            with col2:
                csv_data = final_results_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📄 Tải về file CSV", 
                    data=csv_data,
                    file_name=f"pdf_extraction_results_{total_files}_files_{int(time.time())}.csv",
                    mime="text/csv"
                )
    
    else:
        st.info("👆 Vui lòng tải lên một hoặc nhiều file PDF để bắt đầu.")
        
        # Hiển thị hướng dẫn sử dụng
        with st.expander("📖 Hướng dẫn sử dụng"):
            st.markdown("""
            ### Phiên bản Safe Mode - Tính năng mới:
            - ✅ **Timeout Protection**: Tự động ngắt file xử lý quá lâu
            - ✅ **Memory Management**: Dọn dẹp bộ nhớ sau mỗi file
            - ✅ **Error Recovery**: Tiếp tục xử lý các file khác khi gặp lỗi
            - ✅ **File Size Warning**: Cảnh báo file quá lớn
            - ✅ **Progress Tracking**: Hiển thị thời gian xử lý chi tiết
            - ✅ **Safe File Handling**: Quản lý file tạm thời an toàn
            
            ### Cách sử dụng:
            1. **Tải file PDF**: Click hoặc kéo thả file PDF
            2. **Theo dõi tiến trình**: Xem progress bar và thời gian ước tính
            3. **Xem kết quả realtime**: Kết quả hiển thị ngay khi xử lý xong từng file
            4. **Download kết quả**: Excel hoặc CSV với timestamp
            
            ### Giới hạn và khuyến nghị:
            - File tối đa: 50MB/file
            - Timeout: 120s/file
            - Khuyến nghị: < 20 file/lần để đảm bảo performance
            """)
    
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666; font-size: 0.9em;'>
        PDF Data Extractor v3.0 Safe Mode | Enhanced Error Handling & Performance
        </div>
        """, 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()

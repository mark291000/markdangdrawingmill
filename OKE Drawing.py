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

# --- CÁC HÀM PHỤ TRỢ (LOGIC XỬ LÝ) ---

def find_dimension_lines(lines, tolerance=2):
    horizontal_lines = [line for line in lines if abs(line['y0'] - line['y1']) <= tolerance]
    vertical_lines = [line for line in lines if abs(line['x0'] - line['x1']) <= tolerance]
    return horizontal_lines, vertical_lines

def is_near_dimension_line(number_bbox, h_lines, v_lines, tolerance=15):
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
    return False

def is_bbox_inside_zones(bbox, zones):
    for zone in zones:
        if (max(bbox['x0'], zone['x0']) < min(bbox['x1'], zone['x1']) and max(bbox['top'], zone['top']) < min(bbox['bottom'], zone['bottom'])):
            return True
    return False

def get_ink_area_of_first_char(cluster, page):
    if not cluster: return 0.0
    first_char = cluster[0]
    char_bbox = (first_char['x0'], first_char['top'], first_char['x1'], first_char['bottom'])
    cropped_char_page = page.crop(char_bbox)
    ink_area = 0.0
    for rect in cropped_char_page.rects: ink_area += rect['width'] * rect['height']
    for line in cropped_char_page.lines: ink_area += math.sqrt((line['x1'] - line['x0'])**2 + (line['y1'] - line['y0'])**2) * line.get('linewidth', 1)
    return ink_area

def calculate_confidence(number_info):
    score = 20
    if number_info['is_near_dimension_line']: score += 50
    if number_info['ink_area'] > 15: score += 25
    elif number_info['ink_area'] > 8: score += 15
    if number_info['bbox']['top'] > number_info['page_height'] * 0.85: score -= 40
    if number_info['orientation'] == 'Horizontal': score += 5
    else: score -= 5
    return max(0, min(100, score))

def process_cluster_for_new_logic(cluster, page, orientation, h_lines, v_lines, date_zones):
    if not cluster: return None
    number_str = "".join([c['text'] for c in cluster])
    if orientation == 'Vertical': number_str = number_str[::-1]
    
    if number_str.isdigit() and int(number_str) < 3500:
        value = int(number_str)
        bbox = {'x0': min(c['x0'] for c in cluster), 'top': min(c['top'] for c in cluster), 'x1': max(c['x1'] for c in cluster), 'bottom': max(c['bottom'] for c in cluster)}
        if is_bbox_inside_zones(bbox, date_zones): return None
        ink_area = get_ink_area_of_first_char(cluster, page)
        if ink_area > 200: return None
        is_dim_line = is_near_dimension_line(bbox, h_lines, v_lines)
        number_info = {'value': value, 'bbox': bbox, 'ink_area': ink_area, 'orientation': orientation, 'is_near_dimension_line': is_dim_line, 'page_height': page.height}
        confidence = calculate_confidence(number_info)
        return {'Number': value, 'Ink Area': round(ink_area, 2), 'Confidence (%)': confidence}
    return None

def extract_all_numbers(pdf_path):
    all_numbers_data = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            lines, h_lines, v_lines = page.lines, *find_dimension_lines(page.lines)
            date_zones = page.search(r'\b\d{1,2}/\d{1,2}/\d{4}\b', regex=True)
            h_chars = sorted([c for c in page.chars if c.get("upright", True)], key=lambda c: (round(c["top"], 1), c["x0"]))
            current_cluster, last_char = [], None
            for char in h_chars:
                if char['text'].isdigit():
                    if current_cluster and last_char and (char['x0'] - last_char['x1'] > char.get('size', 8) * 0.6 or abs(char['top'] - last_char['top']) > 2):
                        result = process_cluster_for_new_logic(current_cluster, page, 'Horizontal', h_lines, v_lines, date_zones)
                        if result: all_numbers_data.append(result)
                        current_cluster = [char]
                    else: current_cluster.append(char)
                else:
                    if current_cluster:
                        result = process_cluster_for_new_logic(current_cluster, page, 'Horizontal', h_lines, v_lines, date_zones)
                        if result: all_numbers_data.append(result)
                    current_cluster = []
                last_char = char
            if current_cluster:
                result = process_cluster_for_new_logic(current_cluster, page, 'Horizontal', h_lines, v_lines, date_zones)
                if result: all_numbers_data.append(result)
            v_chars_by_col = defaultdict(list)
            for char in [c for c in page.chars if not c.get("upright", True)]: v_chars_by_col[round(char['x0'], 0)].append(char)
            for col in v_chars_by_col.values():
                col.sort(key=lambda c: c['top'])
                current_cluster, last_char = [], None
                for char in col:
                    if char['text'].isdigit():
                        if current_cluster and last_char and (char['top'] - last_char['bottom'] > char.get('size', 8) * 0.6):
                            result = process_cluster_for_new_logic(current_cluster, page, 'Vertical', h_lines, v_lines, date_zones)
                            if result: all_numbers_data.append(result)
                            current_cluster = [char]
                        else: current_cluster.append(char)
                    else:
                        if current_cluster:
                            result = process_cluster_for_new_logic(current_cluster, page, 'Vertical', h_lines, v_lines, date_zones)
                            if result: all_numbers_data.append(result)
                        current_cluster = []
                    last_char = char
                if current_cluster:
                    result = process_cluster_for_new_logic(current_cluster, page, 'Vertical', h_lines, v_lines, date_zones)
                    if result: all_numbers_data.append(result)
    return all_numbers_data

def assign_ink_groups(df, tolerance=1.0):
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

def find_laminate_keywords(pdf_path):
    target_keywords = ["LAM/MASKING (IF APPLICABLE)","GLUEABLE LAM/TC BLACK (IF APPLICABLE)","FLEX PAPER/PAPER", "GLUEABLE LAM", "RAW", "LAM", "GRAIN"]
    found_pairs = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            chars = page.chars
            if not chars: continue
            chars = sorted(chars, key=lambda c: (round(c["top"], 1), c["x0"]))
            full_text = "".join(c["text"] for c in chars)
            for keyword in target_keywords:
                for pos in [m.start() for m in re.finditer(re.escape(keyword), full_text)]:
                    keyword_chars = chars[pos:pos + len(keyword)]
                    if not keyword_chars: continue
                    keyword_y = sum(c["top"] for c in keyword_chars) / len(keyword_chars)
                    keyword_x_center = sum(c["x0"] for c in keyword_chars) / len(keyword_chars)
                    below_word = find_word_below(chars, keyword_y, keyword_x_center, target_keywords)
                    if below_word: found_pairs.append(f"{keyword}/{below_word}")
                    else: found_pairs.append(keyword)
    return found_pairs

def find_word_below(chars, keyword_y, keyword_x_center, target_keywords, y_tolerance=50, x_tolerance=100):
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
    return None

def process_laminate_result(laminate_string):
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

def find_profile_a(pdf_path):
    profile_value = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                match = re.search(r"PROFILE\s*:*\s*(\S+)", text, re.IGNORECASE)
                if match: return match.group(1)
    return profile_value

def extract_edgeband_and_foil_keywords(pdf_path):
    """
    Quét PDF để đếm và tạo nhãn L và S cho từng danh mục riêng biệt.
    """
    edgeband_L_keywords = {"EDGEBAND"}
    edgeband_S_keywords = {"DNABEGDE"}
    foil_L_keywords = {"FOIL"}
    foil_S_keywords = {"LIOF"}

    edgeband_L_count, edgeband_S_count = 0, 0
    foil_L_count, foil_S_count = 0, 0

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(x_tolerance=2)
            if not words: continue
            
            page_words = [w["text"].upper() for w in words]

            edgeband_L_count += sum(1 for t in page_words if t in edgeband_L_keywords)
            edgeband_S_count += sum(1 for t in page_words if t in edgeband_S_keywords)
            foil_L_count += sum(1 for t in page_words if t in foil_L_keywords)
            foil_S_count += sum(1 for t in page_words if t in foil_S_keywords)
            
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

def check_dimensions_status(length, width, height):
    if (length and str(length) != '' and str(length) != 'ERROR' and width and str(width) != '' and str(width) != 'ERROR' and height and str(height) != '' and str(height) != 'ERROR'):
        return 'Done'
    return 'Recheck'

def process_single_pdf(pdf_path, original_filename):
    numbers = extract_all_numbers(pdf_path)
    
    dim_map = {}
    if numbers:
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

    laminate_pairs = find_laminate_keywords(pdf_path)
    laminate_raw_result = " / ".join(laminate_pairs) if laminate_pairs else ""
    laminate_result = process_laminate_result(laminate_raw_result) if laminate_pairs else ""
    profile_a_result = find_profile_a(pdf_path)
    edgeband_foil_results = extract_edgeband_and_foil_keywords(pdf_path)

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
    
    final_result['Status'] = check_dimensions_status(final_result['Length (mm)'], final_result['Width (mm)'], final_result['Height (mm)'])
    return final_result

def save_uploaded_file(uploaded_file):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            return tmp_file.name
    except Exception as e:
        st.error(f"Error saving file: {str(e)}")
        return None

def to_excel(df):
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
    return output.getvalue()

# ===== GIAO DIỆN STREAMLIT VỚI PROGRESS BAR =====
def main():
    st.title("📄 Trình trích xuất dữ liệu PDF")
    st.write("Tự động nhận diện kích thước (Dài, Rộng, Cao) và các thông tin khác từ bản vẽ kỹ thuật.")

    uploaded_files = st.file_uploader(
        "Kéo và thả file PDF vào đây hoặc nhấn để chọn",
        type="pdf",
        accept_multiple_files=True,
        label_visibility="collapsed"
    )
    
    if uploaded_files:
        all_final_results = []
        total_files = len(uploaded_files)
        
        # Tạo container cho progress và status
        progress_container = st.container()
        
        with progress_container:
            # Tạo progress bar và status text
            progress_bar = st.progress(0)
            status_text = st.empty()
            file_status = st.empty()
        
        # Xử lý từng file
        for i, uploaded_file in enumerate(uploaded_files):
            current_file = i + 1
            
            # Cập nhật trạng thái
            status_text.text(f"⏳ Đang xử lý file {current_file}/{total_files}")
            file_status.info(f"📄 **{uploaded_file.name}**")
            
            temp_path = save_uploaded_file(uploaded_file)
            if temp_path:
                try:
                    final_result = process_single_pdf(temp_path, uploaded_file.name)
                    all_final_results.append(final_result)
                    
                    # Hiển thị kết quả tạm thời cho file vừa xử lý
                    if final_result['Status'] == 'Done':
                        file_status.success(f"✅ **{uploaded_file.name}** - Thành công")
                    else:
                        file_status.warning(f"⚠️ **{uploaded_file.name}** - Cần kiểm tra lại")
                        
                except Exception as e:
                    st.error(f"❌ Lỗi khi xử lý file **{uploaded_file.name}**: {e}")
                    error_result = {
                        'Drawing #': os.path.splitext(uploaded_file.name)[0],
                        'Length (mm)': 'LỖI', 'Width (mm)': 'LỖI', 'Height (mm)': 'LỖI',
                        'Laminate': 'LỖI', 'Edgeband': 'LỖI', 'Foil': 'LỖI',
                        'Profile': 'LỖI', 'Status': 'LỖI'
                    }
                    all_final_results.append(error_result)
                    file_status.error(f"❌ **{uploaded_file.name}** - Lỗi xử lý")
                finally:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
            
            # Cập nhật progress bar
            progress_percentage = current_file / total_files
            progress_bar.progress(progress_percentage)
        
        # Hoàn thành xử lý
        progress_bar.progress(1.0)
        status_text.success(f"✅ Hoàn thành xử lý {total_files} file!")
        file_status.empty()  # Xóa trạng thái file cuối cùng
        
        if all_final_results:
            st.markdown("---")
            
            # Hiển thị thống kê tổng quan
            col1, col2, col3 = st.columns(3)
            with col1:
                done_count = sum(1 for result in all_final_results if result['Status'] == 'Done')
                st.metric("✅ Thành công", done_count)
            with col2:
                recheck_count = sum(1 for result in all_final_results if result['Status'] == 'Recheck')
                st.metric("⚠️ Cần kiểm tra", recheck_count)
            with col3:
                error_count = sum(1 for result in all_final_results if result['Status'] == 'LỖI')
                st.metric("❌ Lỗi", error_count)
            
            st.markdown("---")
            st.subheader("📊 Kết quả trích xuất chi tiết")
            
            final_results_df = pd.DataFrame(all_final_results)
            
            # Tô màu theo status
            def highlight_status(val):
                if val == 'Done':
                    return 'background-color: #d4edda; color: #155724'
                elif val == 'Recheck':
                    return 'background-color: #fff3cd; color: #856404'
                elif val == 'LỖI':
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
                        file_name=f"pdf_extraction_results_{total_files}_files.xlsx",
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
                    file_name=f"pdf_extraction_results_{total_files}_files.csv",
                    mime="text/csv"
                )
    
    else:
        st.info("👆 Vui lòng tải lên một hoặc nhiều file PDF để bắt đầu.")
        
        # Hiển thị hướng dẫn sử dụng
        with st.expander("📖 Hướng dẫn sử dụng"):
            st.markdown("""
            ### Cách sử dụng:
            1. **Tải file PDF**: Click vào vùng upload hoặc kéo thả file PDF vào đây
            2. **Chờ xử lý**: Ứng dụng sẽ tự động phân tích từng file
            3. **Xem kết quả**: Kết quả sẽ hiển thị trong bảng với các thông tin:
               - Drawing #: Tên file (không có phần mở rộng)
               - Length/Width/Height: Kích thước được trích xuất (mm)
               - Laminate: Thông tin laminate
               - Edgeband/Foil: Thông tin edgeband và foil
               - Profile: Thông tin profile
               - Status: Trạng thái (Done/Recheck/Lỗi)
            4. **Tải kết quả**: Sử dụng nút download để lưu kết quả dưới dạng Excel hoặc CSV
            
            ### Lưu ý:
            - Hỗ trợ xử lý nhiều file cùng lúc
            - File PDF phải là bản vẽ kỹ thuật có chứa thông tin kích thước
            - Quá trình xử lý có thể mất vài phút tùy thuộc vào số lượng và kích thước file
            """)
    
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666; font-size: 0.9em;'>
        PDF Data Extractor v2.0 | Built with Streamlit | Progress Tracking Enabled
        </div>
        """, 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()

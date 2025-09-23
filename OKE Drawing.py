import streamlit as st
import pdfplumber
import pandas as pd
import re
import numpy as np
from collections import Counter
import math
import io

# =============================================================================
# ENHANCED NUMBER EXTRACTION FUNCTIONS
# =============================================================================

def reverse_number_string(number_string):
    """Đảo ngược chuỗi số"""
    return number_string[::-1]

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
        st.error(f"Error extracting FOIL classification: {e}")
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
        st.error(f"Error extracting EDGEBAND classification: {e}")
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
        st.error(f"Error extracting profile: {e}")
        return ""

def extract_numbers_from_chars_corrected_no_duplicates(page):
    """METHOD: Corrected character-level extraction with no duplicates"""
    numbers = []
    orientations = {}
    font_info = {}

    try:
        chars = page.chars
        digit_chars = [c for c in chars if c['text'].isdigit()]

        if not digit_chars:
            return numbers, orientations, font_info

        char_groups = create_character_groups_improved(digit_chars)
        extracted_numbers = set()

        for group in char_groups:
            if len(group) == 1:
                try:
                    num_value = int(group[0]['text'])
                    if 1 <= num_value <= 9999 and num_value not in extracted_numbers:
                        numbers.append(num_value)
                        orientations[num_value] = 'Single'
                        font_info[num_value] = {
                            'chars': group,
                            'fontname': group[0].get('fontname', 'Unknown')
                        }
                        extracted_numbers.add(num_value)
                except:
                    continue
            else:
                result = process_character_group_smart(group, extracted_numbers)
                if result:
                    number, orientation = result
                    numbers.append(number)
                    orientations[number] = orientation
                    fonts = [ch.get("fontname", "Unknown") for ch in group]
                    fontname = Counter(fonts).most_common(1)[0][0] if fonts else "Unknown"
                    font_info[number] = {
                        'chars': group,
                        'fontname': fontname
                    }
                    extracted_numbers.add(number)

    except Exception as e:
        st.error(f"Error in char extraction: {e}")

    return numbers, orientations, font_info

def create_character_groups_improved(digit_chars):
    """Tạo các nhóm ký tự với logic cải thiện để tránh trùng lặp"""
    char_groups = []
    used_chars = set()

    sorted_chars = sorted(digit_chars, key=lambda c: (c['top'], c['x0']))

    for i, base_char in enumerate(sorted_chars):
        if id(base_char) in used_chars:
            continue

        current_group = [base_char]
        used_chars.add(id(base_char))

        for j, other_char in enumerate(sorted_chars):
            if i == j or id(other_char) in used_chars:
                continue

            if should_group_characters(base_char, other_char, current_group):
                current_group.append(other_char)
                used_chars.add(id(other_char))

        if len(current_group) >= 1:
            char_groups.append(current_group)

    return char_groups

def should_group_characters(base_char, other_char, current_group):
    """Xác định xem 2 ký tự có nên được nhóm lại không"""
    try:
        distance = math.sqrt(
            (base_char['x0'] - other_char['x0'])**2 +
            (base_char['top'] - other_char['top'])**2
        )

        if distance > 25:
            return False

        if len(current_group) > 1:
            group_x_span = max(c['x0'] for c in current_group) - min(c['x0'] for c in current_group)
            group_y_span = max(c['top'] for c in current_group) - min(c['top'] for c in current_group)

            is_group_vertical = group_y_span > group_x_span * 1.5

            if is_group_vertical:
                group_x_center = sum(c['x0'] for c in current_group) / len(current_group)
                if abs(other_char['x0'] - group_x_center) > 8:
                    return False
            else:
                group_y_center = sum(c['top'] for c in current_group) / len(current_group)
                if abs(other_char['top'] - group_y_center) > 6:
                    return False

        return True

    except Exception:
        return False

def process_character_group_smart(group, extracted_numbers):
    """Xử lý nhóm ký tự thông minh để tránh trùng lặp"""
    try:
        if len(group) < 2:
            return None

        x_positions = [c['x0'] for c in group]
        y_positions = [c['top'] for c in group]

        x_span = max(x_positions) - min(x_positions)
        y_span = max(y_positions) - min(y_positions)

        is_vertical = y_span > x_span * 1.5

        if is_vertical:
            vertical_sorted = sorted(group, key=lambda c: c['top'])
            v_text = "".join([c['text'] for c in vertical_sorted])

            candidates = []

            try:
                num_original = int(v_text)
                if 1 <= num_original <= 9999 and num_original not in extracted_numbers:
                    candidates.append((num_original, 'Vertical'))
            except:
                pass

            try:
                reversed_v_text = reverse_number_string(v_text)
                num_reversed = int(reversed_v_text)
                if 1 <= num_reversed <= 9999 and num_reversed not in extracted_numbers:
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
                if 1 <= num_value <= 9999 and num_value not in extracted_numbers:
                    return (num_value, 'Horizontal')
            except:
                pass

        return None

    except Exception:
        return None

def create_dimension_summary(df):
    """Tạo bảng tóm tắt với Profile ở cuối"""
    if len(df) == 0:
        return pd.DataFrame(columns=["Drawing#", "Length (mm)", "Width (mm)", "Height (mm)", "FOIL", "EDGEBAND", "Profile"])
    
    df_sorted = df.sort_values("Number_Int", ascending=False).reset_index(drop=True)
    
    length_number = ""
    width_number = ""
    height_number = ""
    
    for i, row in df_sorted.iterrows():
        number_value = int(row['Number_Int'])
        
        if i == 0:
            length_number = str(number_value)
        elif i == len(df_sorted) - 1:
            height_number = str(number_value)
        elif i == len(df_sorted) - 2:
            width_number = str(number_value)
    
    filename = df.iloc[0]['File']
    drawing_name = filename.replace('.pdf', '') if filename.endswith('.pdf') else filename
    
    profile_info = df.iloc[0]['Profile'] if 'Profile' in df.columns else ""
    foil_info = df.iloc[0]['FOIL'] if 'FOIL' in df.columns else ""
    edgeband_info = df.iloc[0]['EDGEBAND'] if 'EDGEBAND' in df.columns else ""
    
    return pd.DataFrame({
        "Drawing#": [drawing_name],
        "Length (mm)": [length_number],
        "Width (mm)": [width_number], 
        "Height (mm)": [height_number],
        "FOIL": [foil_info],
        "EDGEBAND": [edgeband_info],
        "Profile": [profile_info]
    })

def extract_font_number(fontname):
    """Trích xuất số từ font name"""
    m = re.search(r"F(\d+)$", fontname)
    return int(m.group(1)) if m else -1

def process_pdf_files(uploaded_files):
    """Xử lý các file PDF được upload"""
    results = []
    
    for uploaded_file in uploaded_files:
        try:
            # Đọc file PDF từ uploaded file
            with pdfplumber.open(uploaded_file) as pdf:
                total_pages = len(pdf.pages)

                if total_pages == 0:
                    continue

                page = pdf.pages[0]

                # Trích xuất thông tin
                profile_info = extract_profile_from_page(page)
                foil_classification, foil_detail = extract_foil_classification_with_detail(page)
                edgeband_classification, edgeband_detail = extract_edgeband_classification_with_detail(page)

                char_numbers, char_orientations, font_info = extract_numbers_from_chars_corrected_no_duplicates(page)

                if not char_numbers:
                    continue

                # Xử lý kết quả
                for number in char_numbers:
                    orientation = char_orientations.get(number, 'Horizontal')
                    fontname = font_info.get(number, {}).get('fontname', 'Unknown')
                    
                    results.append({
                        "File": uploaded_file.name,
                        "Number": str(number),
                        "Font Name": fontname,
                        "Orientation": orientation,
                        "Number_Int": number,
                        "Profile": profile_info,
                        "FOIL": foil_classification,
                        "EDGEBAND": edgeband_classification
                    })
        
        except Exception as e:
            st.error(f"Error processing file {uploaded_file.name}: {e}")
            continue
    
    return results

# =============================================================================
# STREAMLIT INTERFACE
# =============================================================================

def main():
    st.set_page_config(
        page_title="PDF Data Extraction Tool",
        page_icon="📄",
        layout="wide"
    )
    
    st.title("📄 PDF Data Extraction Tool")
    st.markdown("---")
    
    # Initialize session state
    if 'results_df' not in st.session_state:
        st.session_state.results_df = None
    if 'detail_df' not in st.session_state:
        st.session_state.detail_df = None
    
    # File upload section
    st.header("📁 Upload PDF Files")
    uploaded_files = st.file_uploader(
        "Choose PDF files",
        type=['pdf'],
        accept_multiple_files=True,
        help="Select one or more PDF files to process"
    )
    
    # Control buttons
    col1, col2 = st.columns([1, 1])
    
    with col1:
        run_button = st.button(
            "🚀 RUN",
            type="primary",
            disabled=(uploaded_files is None or len(uploaded_files) == 0),
            use_container_width=True
        )
    
    with col2:
        reset_button = st.button(
            "🔄 RESET",
            use_container_width=True
        )
    
    # Reset functionality
    if reset_button:
        st.session_state.results_df = None
        st.session_state.detail_df = None
        st.rerun()
    
    # Processing
    if run_button and uploaded_files:
        with st.spinner("Processing PDF files..."):
            # Process files
            results = process_pdf_files(uploaded_files)
            
            if results:
                # Create DataFrame and remove duplicates
                df_all = pd.DataFrame(results).drop_duplicates().reset_index(drop=True)
                
                # Logic font name - keep highest font number
                df_all["Font_Num"] = df_all["Font Name"].apply(extract_font_number)
                
                df_final = df_all.groupby("File", as_index=False).apply(
                    lambda g: g[g["Font_Num"] == g["Font_Num"].max()]
                ).reset_index(drop=True)
                
                df_final = df_final.drop(columns=["Font_Num"])
                
                # Create summary
                summary_results = []
                for file_group in df_final.groupby("File"):
                    filename, file_data = file_group
                    summary = create_dimension_summary(file_data)
                    summary_results.append(summary)
                
                final_summary = pd.concat(summary_results, ignore_index=True) if summary_results else pd.DataFrame(columns=["Drawing#", "Length (mm)", "Width (mm)", "Height (mm)", "FOIL", "EDGEBAND", "Profile"])
                
                # Store in session state
                st.session_state.results_df = final_summary
                st.session_state.detail_df = df_final[["File", "Number", "Font Name", "FOIL", "EDGEBAND", "Profile"]]
                
                st.success(f"Successfully processed {len(uploaded_files)} PDF file(s)!")
            else:
                st.warning("No data could be extracted from the uploaded files.")
    
    # Display results
    if st.session_state.results_df is not None:
        st.markdown("---")
        st.header("📊 Results")
        
        # Rules explanation
        with st.expander("📋 Processing Rules", expanded=False):
            st.markdown("""
            **Classification Rules:**
            - **FOIL** = L (Long), **LIOF** = S (Short)
            - **EDGEBAND** = L (Long), **DNABEGDE** = S (Short)
            - Maximum: 2L2S for each type
            
            **Dimension Assignment:**
            - **Length**: Largest number found
            - **Width**: Second largest number found  
            - **Height**: Smallest number found
            """)
        
        # Main results table
        st.subheader("📈 Final Summary")
        st.dataframe(
            st.session_state.results_df,
            use_container_width=True,
            hide_index=True
        )
        
        # Download button
        csv = st.session_state.results_df.to_csv(index=False)
        st.download_button(
            label="📥 Download Results as CSV",
            data=csv,
            file_name="pdf_extraction_results.csv",
            mime="text/csv"
        )
        
        # Detail table
        with st.expander("🔍 Detailed Information", expanded=False):
            st.subheader("Detail Data (for verification)")
            st.dataframe(
                st.session_state.detail_df,
                use_container_width=True,
                hide_index=True
            )

if __name__ == "__main__":
    main()

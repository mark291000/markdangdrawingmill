import streamlit as st
import pdfplumber
import re
import pandas as pd
from collections import defaultdict
import os
import tempfile

# Set page config
st.set_page_config(
    page_title="PDF Data Extractor",
    page_icon="📄",
    layout="wide"
)

def has_nearby_line(num_chars, lines, tolerance=3):
    """
    Check if there is a horizontal or vertical line near the number.
    Improved: Check if the number is between two lines.
    """
    if not num_chars:
        return False

    # Bounding box coordinates of the number
    x0 = min(c["x0"] for c in num_chars)
    x1 = max(c["x1"] for c in num_chars)
    y0 = min(c["top"] for c in num_chars)
    y1 = max(c["bottom"] for c in num_chars)

    center_x = (x0 + x1) / 2
    center_y = (y0 + y1) / 2

    horizontal_lines = []
    vertical_lines = []

    # Classify lines
    for line in lines:
        line_length = max(abs(line["x1"] - line["x0"]), abs(line["y1"] - line["y0"]))
        if line_length < 5:  # Ignore very short lines
            continue

        # Horizontal line (y is almost constant)
        if abs(line["y0"] - line["y1"]) <= tolerance:
            horizontal_lines.append(line)
        # Vertical line (x is almost constant)
        elif abs(line["x0"] - line["x1"]) <= tolerance:
            vertical_lines.append(line)

    # Check if the number is between 2 horizontal lines
    horizontal_between = False
    relevant_h_lines = [l for l in horizontal_lines
                       if min(l["x0"], l["x1"]) <= center_x <= max(l["x0"], l["x1"])]

    if len(relevant_h_lines) >= 2:
        y_positions = [l["y0"] for l in relevant_h_lines]
        y_positions.sort()
        for i in range(len(y_positions) - 1):
            if y_positions[i] <= center_y <= y_positions[i + 1]:
                horizontal_between = True
                break

    # Check if the number is between 2 vertical lines
    vertical_between = False
    relevant_v_lines = [l for l in vertical_lines
                       if min(l["y0"], l["y1"]) <= center_y <= max(l["y0"], l["y1"])]

    if len(relevant_v_lines) >= 2:
        x_positions = [l["x0"] for l in relevant_v_lines]
        x_positions.sort()
        for i in range(len(x_positions) - 1):
            if x_positions[i] <= center_x <= x_positions[i + 1]:
                vertical_between = True
                break

    # Check for a nearby line (original logic as a backup)
    nearby_line = False
    for line in lines:
        # Horizontal line
        if abs(line["y0"] - line["y1"]) <= tolerance:
            line_x_min = min(line["x0"], line["x1"])
            line_x_max = max(line["x0"], line["x1"])
            if (line_x_min <= x1 + tolerance and line_x_max >= x0 - tolerance):
                if abs(line["y0"] - y0) <= tolerance or abs(line["y0"] - y1) <= tolerance:
                    nearby_line = True
                    break

        # Vertical line
        elif abs(line["x0"] - line["x1"]) <= tolerance:
            line_y_min = min(line["y0"], line["y1"])
            line_y_max = max(line["y0"], line["y1"])
            if (line_y_min <= y1 + tolerance and line_y_max >= y0 - tolerance):
                if abs(line["x0"] - x0) <= tolerance or abs(line["x0"] - x1) <= tolerance:
                    nearby_line = True
                    break

    return horizontal_between or vertical_between or nearby_line


def extract_numbers_from_chars(chars, lines, page_num):
    """Extract numbers < 3500 with horizontal and vertical handling - GETS BOTH Line Yes and No"""
    
    numbers_found = []

    # ===== Process horizontal text (NO reversal) =====
    horizontal_chars = [c for c in chars if c.get("upright", True)]
    if horizontal_chars:
        # Sort by natural reading order (left -> right, top -> bottom)
        horizontal_chars.sort(key=lambda c: (round(c["top"], 1), c["x0"]))
        text_horizontal = "".join(c["text"] for c in horizontal_chars)

        # Find all numbers in the text
        for match in re.finditer(r"\d+", text_horizontal):
            number_str = match.group()  # KEEP horizontal number as is
            if number_str.isdigit() and int(number_str) < 3500:
                start_idx, end_idx = match.span()
                number_chars = horizontal_chars[start_idx:end_idx]

                if number_chars:
                    # Check if there is a line nearby
                    has_line = has_nearby_line(number_chars, lines)
                    line_status = "Yes" if has_line else "No"

                    font_size = round(number_chars[0].get("size", 0), 2)

                    # Calculate Y position for top-down sorting
                    avg_y = sum(c["top"] for c in number_chars) / len(number_chars)

                    numbers_found.append({
                        "Page": page_num,
                        "Number": number_str,
                        "Direction": "Horizontal",
                        "Boldness": font_size,
                        "Line": line_status,
                        "Y_Position": avg_y
                    })

    # ===== Process vertical text (REVERSE) =====
    vertical_chars = [c for c in chars if not c.get("upright", True)]
    if vertical_chars:
        # Group by column (similar x position)
        columns = defaultdict(list)
        for char in vertical_chars:
            col_key = round(char["x0"], 1)
            columns[col_key].append(char)

        # Process each column
        for col_x, col_chars in columns.items():
            # Sort from top to bottom
            col_chars.sort(key=lambda c: c["y0"])
            text_vertical = "".join(c["text"] for c in col_chars)

            # Find and reverse numbers (only for vertical text)
            for match in re.finditer(r"\d+", text_vertical):
                original_number = match.group()

                if original_number.isdigit() and int(original_number) < 3500:
                    start_idx, end_idx = match.span()
                    number_chars = col_chars[start_idx:end_idx]

                    if number_chars:
                        # Check if there is a line nearby
                        has_line = has_nearby_line(number_chars, lines)
                        line_status = "Yes" if has_line else "No"

                        font_size = round(number_chars[0].get("size", 0), 2)

                        # Calculate Y position for top-down sorting
                        avg_y = sum(c["y0"] for c in number_chars) / len(number_chars)

                        numbers_found.append({
                            "Page": page_num,
                            "Number": original_number,
                            "Direction": "Vertical",
                            "Boldness": font_size,
                            "Line": line_status,
                            "Y_Position": avg_y
                        })
    
    return numbers_found


def find_laminate_keywords(pdf_path):
    """
    Find keywords in priority order: FLEX PAPER/PAPER, GLUEABLE LAM, LAM, RAW, GRAIN
    and the word below them.
    """
    target_keywords = ["LAM/MASKING (IF APPLICABLE)","GLUEABLE LAM/TC BLACK (IF APPLICABLE)","FLEX PAPER/PAPER", "GLUEABLE LAM", "LAM", "RAW", "GRAIN"]
    found_pairs = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            chars = page.chars
            if not chars:
                continue

            # Sort chars by position for correct reading order
            chars = sorted(chars, key=lambda c: (round(c["top"], 1), c["x0"]))

            # Join into text to find keywords
            full_text = "".join(c["text"] for c in chars)

            # Find each keyword in priority order
            for keyword in target_keywords:
                # Find the position of the keyword in the text
                keyword_positions = []
                start = 0
                while True:
                    pos = full_text.find(keyword, start)
                    if pos == -1:
                        break
                    keyword_positions.append(pos)
                    start = pos + 1

                # For each found position of the keyword
                for pos in keyword_positions:
                    # Find chars corresponding to the keyword
                    keyword_chars = chars[pos:pos + len(keyword)]
                    if not keyword_chars:
                        continue

                    # Calculate the Y position of the keyword
                    keyword_y = sum(c["top"] for c in keyword_chars) / len(keyword_chars)
                    keyword_x_center = sum(c["x0"] for c in keyword_chars) / len(keyword_chars)

                    # Find the word below the keyword
                    below_word = find_word_below(chars, keyword_y, keyword_x_center, target_keywords)

                    if below_word:
                        pair = f"{keyword}/{below_word}"
                        found_pairs.append(pair)
                    else:
                        # If no suitable word found below, just take the keyword
                        found_pairs.append(keyword)

    return found_pairs


def find_word_below(chars, keyword_y, keyword_x_center, target_keywords, y_tolerance=50, x_tolerance=100):
    """
    Find a suitable keyword located below the given keyword in priority order.
    """
    # Filter for chars below the keyword
    chars_below = [c for c in chars if c["top"] > keyword_y + 5]  # +5 to avoid getting the keyword itself

    if not chars_below:
        return None

    # Sort by Y distance (closest first)
    chars_below.sort(key=lambda c: c["top"])

    # Group chars by line (similar Y position)
    lines = []
    current_line = []
    current_y = None

    for char in chars_below:
        if current_y is None or abs(char["top"] - current_y) <= 3:  # Same line
            current_line.append(char)
            current_y = char["top"]
        else:
            if current_line:
                lines.append(current_line)
            current_line = [char]
            current_y = char["top"]

    if current_line:
        lines.append(current_line)

    # Check each line from top to bottom
    for line_chars in lines:
        line_chars.sort(key=lambda c: c["x0"])  # Sort by X within the line
        line_text = "".join(c["text"] for c in line_chars).strip()

        # Check keywords in priority order
        for keyword in target_keywords:
            if keyword in line_text:
                # Check if the X position is close to the original keyword
                line_x_center = sum(c["x0"] for c in line_chars) / len(line_chars)
                if abs(line_x_center - keyword_x_center) <= x_tolerance:
                    return keyword

    return None


def process_laminate_result(laminate_string):
    """
    Process the Laminate string to prioritize keywords based on target_keywords order.
    Keep only the highest priority cluster.
    """
    target_keywords = ["FLEX PAPER/PAPER", "GLUEABLE LAM", "LAM", "RAW", "GRAIN"]
    
    if not laminate_string or laminate_string.strip() == "":
        return ""

    # Split the string by " / " to get individual parts
    parts = [part.strip() for part in laminate_string.split(" / ")]

    if not parts:
        return ""

    # Find all clusters (parts containing "/")
    clusters = [part for part in parts if "/" in part]
    
    # If no clusters found, find the highest priority single keyword
    if not clusters:
        for keyword in target_keywords:
            if keyword in parts:
                return keyword
        # If no priority keyword found, return the last part
        return parts[-1] if parts else ""
    
    # Find the highest priority cluster
    best_cluster = ""
    best_priority = float('inf')
    
    for cluster in clusters:
        # Extract keywords from the cluster
        cluster_keywords = cluster.split("/")
        cluster_priority = float('inf')
        
        # Find the highest priority (lowest index) keyword in this cluster
        for keyword in cluster_keywords:
            keyword = keyword.strip()
            if keyword in target_keywords:
                priority = target_keywords.index(keyword)
                if priority < cluster_priority:
                    cluster_priority = priority
        
        # If this cluster has higher priority than current best
        if cluster_priority < best_priority:
            best_priority = cluster_priority
            best_cluster = cluster
    
    # If no priority cluster found, return the last cluster
    if not best_cluster:
        best_cluster = clusters[-1]
    
    return best_cluster


def find_profile_a(pdf_path):
    """
    Find the keyword PROFILE and extract the value after it.
    Example: PROFILE: 0109P-A -> 0109P-A
    """
    profile_value = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                # Use regex to find "PROFILE", optional colon, and capture the next word
                match = re.search(r"PROFILE\s*:*\s*(\S+)", text, re.IGNORECASE)
                if match:
                    profile_value = match.group(1)
                    return profile_value  # Return the first match found
    return profile_value


def extract_edgeband_and_foil_keywords(pdf_path):
    """
    Đếm từ khóa với logic mới:
    - EDGEBAND, FOIL được đếm thành L
    - DNABEGDE, LIOF được đếm thành S
    - Nếu tìm được cả EDGEBAND và DNABEGDE thì ghi là xLyS vào cột EDGEBAND
    - Nếu tìm được cả FOIL và LIOF thì ghi là xLyS vào cột FOIL
    """
    edgeband_L_keywords = {"EDGEBAND"}    # L type for Edgeband
    edgeband_S_keywords = {"DNABEGDE"}    # S type for Edgeband
    foil_L_keywords = {"FOIL"}            # L type for Foil
    foil_S_keywords = {"LIOF"}            # S type for Foil

    edgeband_L_count = 0
    edgeband_S_count = 0
    foil_L_count = 0
    foil_S_count = 0

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            if not words:
                continue

            texts = [w["text"].upper() for w in words]

            # Count Edgeband keywords
            edgeband_L_count += sum(1 for t in texts if t in edgeband_L_keywords)
            edgeband_S_count += sum(1 for t in texts if t in edgeband_S_keywords)
            
            # Count Foil keywords
            foil_L_count += sum(1 for t in texts if t in foil_L_keywords)
            foil_S_count += sum(1 for t in texts if t in foil_S_keywords)

    # Apply limits (max 2 for each type)
    edgeband_L_count = min(edgeband_L_count, 2)
    edgeband_S_count = min(edgeband_S_count, 2)
    foil_L_count = min(foil_L_count, 2)
    foil_S_count = min(foil_S_count, 2)

    # Format results based on what was found
    edgeband_result = ""
    if edgeband_L_count > 0 and edgeband_S_count > 0:
        # Both L and S found for Edgeband -> combine as xLyS
        edgeband_result = f"{edgeband_L_count}L{edgeband_S_count}S"
    elif edgeband_L_count > 0:
        # Only L found for Edgeband
        edgeband_result = f"{edgeband_L_count}L"
    elif edgeband_S_count > 0:
        # Only S found for Edgeband
        edgeband_result = f"{edgeband_S_count}S"

    foil_result = ""
    if foil_L_count > 0 and foil_S_count > 0:
        # Both L and S found for Foil -> combine as xLyS
        foil_result = f"{foil_L_count}L{foil_S_count}S"
    elif foil_L_count > 0:
        # Only L found for Foil
        foil_result = f"{foil_L_count}L"
    elif foil_S_count > 0:
        # Only S found for Foil
        foil_result = f"{foil_S_count}S"

    return {
        'Edgeband': edgeband_result,
        'Foil': foil_result
    }


def check_dimensions_status(length, width, height):
    """
    Check if all three dimensions are present and not empty.
    Return 'Done' if all three are present, 'Recheck' otherwise.
    """
    # Check if all three dimensions have values (not empty strings and not 'ERROR')
    if (length and length != '' and length != 'ERROR' and
        width and width != '' and width != 'ERROR' and
        height and height != '' and height != 'ERROR'):
        return 'Done'
    else:
        return 'Recheck'


def process_single_pdf(pdf_path):
    """Process a single PDF file and return the results"""
    all_numbers = []
    
    # ===== Process PDF =====
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        for page_num, page in enumerate(pdf.pages, start=1):
            chars = page.chars
            lines = page.lines

            if chars:
                page_numbers = extract_numbers_from_chars(chars, lines, page_num)
                all_numbers.extend(page_numbers)

    # ===== Find Laminate keywords =====
    laminate_pairs = find_laminate_keywords(pdf_path)
    laminate_raw_result = " / ".join(laminate_pairs) if laminate_pairs else ""

    if laminate_pairs:
        # Process to keep only the highest priority cluster
        laminate_result = process_laminate_result(laminate_raw_result)
    else:
        laminate_result = ""

    # ===== Find Profile A =====
    profile_a_result = find_profile_a(pdf_path)

    # ===== Find Edgeband and Foil using new combined logic =====
    edgeband_foil_results = extract_edgeband_and_foil_keywords(pdf_path)

    # ===== Create DataFrame and process Result column =====
    if all_numbers:
        df = pd.DataFrame(all_numbers)

        # STEP 1: Sort with Line = Yes first, then by Page and Y_Position
        df = df.sort_values(by=['Line', 'Page', 'Y_Position'],
                           key=lambda x: x.map({'Yes': 0, 'No': 1}) if x.name == 'Line' else x)

        # STEP 2: Find the first valid Boldness from top to bottom
        valid_values = [12.2, 8.01, 9.02, 6.01, 11.90, 7.93, 12.98, 8.65]
        allowed_group = None

        for idx, row in df.iterrows():
            if row['Boldness'] in valid_values:
                first_boldness = row['Boldness']

                if first_boldness in [12.02, 8.01]:
                    allowed_group = [12.02, 8.01]
                elif first_boldness in [9.02, 6.01]:
                    allowed_group = [9.02, 6.01]
                elif first_boldness in [11.90, 7.93]:
                    allowed_group = [11.90, 7.93]
                elif first_boldness in [12.98, 8.65]:
                    allowed_group = [12.98, 8.65]
                break

        # STEP 3: Mark up to 3 numbers as "correct"
        df['Result'] = ''
        correct_count = 0

        if allowed_group:
            for idx, row in df.iterrows():
                if correct_count >= 3:
                    break

                if row['Boldness'] in allowed_group:
                    df.at[idx, 'Result'] = 'correct'
                    correct_count += 1

        # ===== STEP 4: Add Status column for rows with Result = 'correct' =====
        df['Status'] = ''

        # Get the list of 'correct' numbers
        correct_rows = df[df['Result'] == 'correct'].copy()

        if len(correct_rows) > 0:
            # Convert Number to int for comparison
            correct_rows['Number_Int'] = correct_rows['Number'].astype(int)

            # Sort by numeric value to determine order
            sorted_numbers = correct_rows['Number_Int'].sort_values().tolist()

            # Get unique numbers and their counts
            unique_numbers = list(set(sorted_numbers))
            unique_numbers.sort()

            if len(unique_numbers) == 1:
                # Only one unique number (can be repeated)
                number = unique_numbers[0]
                # Assign all possible statuses
                correct_indices = df[(df['Result'] == 'correct') & (df['Number'].astype(int) == number)].index.tolist()
                if len(correct_indices) >= 1:
                    df.at[correct_indices[0], 'Status'] = 'Length'
                if len(correct_indices) >= 2:
                    df.at[correct_indices[1], 'Status'] = 'Width'
                if len(correct_indices) >= 3:
                    df.at[correct_indices[2], 'Status'] = 'Height'

            elif len(unique_numbers) == 2:
                # Two different numbers
                smaller = unique_numbers[0]
                larger = unique_numbers[1]

                # Assign Length to the largest number
                larger_indices = df[(df['Result'] == 'correct') & (df['Number'].astype(int) == larger)].index.tolist()
                if larger_indices:
                    df.at[larger_indices[0], 'Status'] = 'Length'

                # Assign Width and Height to the smaller number
                smaller_indices = df[(df['Result'] == 'correct') & (df['Number'].astype(int) == smaller)].index.tolist()
                if len(smaller_indices) >= 1:
                    df.at[smaller_indices[0], 'Status'] = 'Width'
                if len(smaller_indices) >= 2:
                    df.at[smaller_indices[1], 'Status'] = 'Height'

            else:
                # Three or more different numbers
                largest = unique_numbers[-1]    # Largest number
                smallest = unique_numbers[0]    # Smallest number
                middle = unique_numbers[1]      # Middle number

                # Assign Status by order of appearance in the DataFrame
                df.loc[(df['Result'] == 'correct') & (df['Number'].astype(int) == largest), 'Status'] = 'Length'
                df.loc[(df['Result'] == 'correct') & (df['Number'].astype(int) == middle), 'Status'] = 'Width'
                df.loc[(df['Result'] == 'correct') & (df['Number'].astype(int) == smallest), 'Status'] = 'Height'

    # ===== Create final result row =====
    # Get filename without extension
    drawing_name = os.path.splitext(os.path.basename(pdf_path))[0]

    # Initialize dictionary for the final result
    final_result = {
        'Drawing #': drawing_name,
        'Length (mm)': '',
        'Width (mm)': '',
        'Height (mm)': '',
        'Laminate': laminate_result,
        'Edgeband': edgeband_foil_results['Edgeband'],
        'Foil': edgeband_foil_results['Foil'],
        'Profile': profile_a_result
    }

    # Fill all available Status values
    if all_numbers:
        correct_with_status = df[df['Result'] == 'correct']

        # Create dictionary to store all values by Status
        status_values = {'Length': [], 'Width': [], 'Height': []}

        for _, row in correct_with_status.iterrows():
            if row['Status'] in status_values:
                status_values[row['Status']].append(row['Number'])

        # Fill final_result - take the first value if there are multiple
        if status_values['Length']:
            final_result['Length (mm)'] = status_values['Length'][0]
        if status_values['Width']:
            final_result['Width (mm)'] = status_values['Width'][0]
        if status_values['Height']:
            final_result['Height (mm)'] = status_values['Height'][0]

    # ===== Add Status column at the end =====
    dimensions_status = check_dimensions_status(
        final_result['Length (mm)'], 
        final_result['Width (mm)'], 
        final_result['Height (mm)']
    )
    final_result['Status'] = dimensions_status

    return final_result, all_numbers


def save_uploaded_file(uploaded_file):
    """Save uploaded file to temporary location and return path"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            return tmp_file.name
    except Exception as e:
        st.error(f"Error saving file: {str(e)}")
        return None


# ===== STREAMLIT UI =====
def main():
    st.title("📄 PDF Data Extractor")
    st.markdown("---")
    
    # Introduction
    st.markdown("""
    ### Upload PDF files to extract:
    - **Dimensions**: Length, Width, Height
    - **Laminate** information
    - **Edgeband** and **Foil** data
    - **Profile** information
    """)
    
    # File uploader
    uploaded_files = st.file_uploader(
        "Choose PDF files", 
        type="pdf", 
        accept_multiple_files=True,
        help="Select one or more PDF files to process"
    )
    
    if uploaded_files:
        st.success(f"Selected {len(uploaded_files)} file(s)")
        
        # Process button
        if st.button("🚀 Process Files", type="primary"):
            all_final_results = []
            
            # Progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            total_files = len(uploaded_files)
            
            for i, uploaded_file in enumerate(uploaded_files):
                # Update progress
                progress = (i + 1) / total_files
                progress_bar.progress(progress)
                status_text.text(f"Processing: {uploaded_file.name} ({i+1}/{total_files})")
                
                # Save uploaded file to temporary location
                temp_path = save_uploaded_file(uploaded_file)
                
                if temp_path:
                    try:
                        final_result, all_numbers = process_single_pdf(temp_path)
                        all_final_results.append(final_result)
                        
                        # Clean up temporary file
                        os.unlink(temp_path)
                        
                    except Exception as e:
                        st.error(f"Error processing {uploaded_file.name}: {str(e)}")
                        # Add error result
                        error_result = {
                            'Drawing #': os.path.splitext(uploaded_file.name)[0],
                            'Length (mm)': 'ERROR',
                            'Width (mm)': 'ERROR',
                            'Height (mm)': 'ERROR',
                            'Laminate': 'ERROR',
                            'Edgeband': 'ERROR',
                            'Foil': 'ERROR',
                            'Profile': 'ERROR',
                            'Status': 'ERROR'
                        }
                        all_final_results.append(error_result)
                        
                        # Clean up temporary file
                        if temp_path and os.path.exists(temp_path):
                            os.unlink(temp_path)
            
            # Clear progress indicators
            progress_bar.empty()
            status_text.empty()
            
            # Display results
            if all_final_results:
                st.markdown("---")
                st.subheader("📊 Final Results")
                
                # Create DataFrame
                final_results_df = pd.DataFrame(all_final_results)
                
                # Display table
                st.dataframe(
                    final_results_df,
                    use_container_width=True,
                    hide_index=True
                )
                
                # Summary statistics
                st.markdown("---")
                st.subheader("📈 Summary Statistics")
                
                col1, col2, col3, col4 = st.columns(4)
                
                # Calculate statistics
                total_files = len(all_final_results)
                successful_files = len([r for r in all_final_results if r['Length (mm)'] != 'ERROR'])
                error_files = total_files - successful_files
                done_files = len([r for r in all_final_results if r['Status'] == 'Done'])
                recheck_files = len([r for r in all_final_results if r['Status'] == 'Recheck'])
                
                with col1:
                    st.metric("Total Files", total_files)
                
                with col2:
                    st.metric("Successful", successful_files, delta=None if error_files == 0 else f"-{error_files}")
                
                with col3:
                    st.metric("Complete (Done)", done_files, delta_color="normal")
                
                with col4:
                    st.metric("Need Review", recheck_files, delta_color="inverse")
                
                # Download button for CSV
                st.markdown("---")
                csv = final_results_df.to_csv(index=False)
                st.download_button(
                    label="💾 Download Results as CSV",
                    data=csv,
                    file_name="pdf_extraction_results.csv",
                    mime="text/csv"
                )
                
                # Status color coding info
                st.markdown("---")
                st.markdown("### 🎨 Status Legend")
                col1, col2 = st.columns(2)
                with col1:
                    st.success("**Done**: All dimensions extracted successfully")
                with col2:
                    st.warning("**Recheck**: Missing one or more dimensions")
                
            else:
                st.error("No results to display!")
    
    else:
        st.info("👆 Please upload PDF files to get started")
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666; font-size: 0.9em;'>
        PDF Data Extractor | Built with Streamlit
        </div>
        """, 
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()

import pandas as pd

# Function to read CSV, create a set of GUIDs, and remove GUIDs with errors
def filter_guid_errors(file_path):
    try:
        # Read the CSV file
        df = pd.read_csv(file_path)

        # Check if the required columns exist
        if 'GUID' not in df.columns or 'output' not in df.columns:
            return "The required columns ('GUID' or 'output') were not found in the CSV."

        # Create a set of all unique GUIDs
        guid_set = set(df['GUID'].unique())
        print(f"{len(guid_set)} total GUIDs")

        # Set to store GUIDs with errors
        guids_with_errors = set()

        # Iterate through the DataFrame and remove GUIDs with errors in the 'output' column
        for guid in guid_set.copy():  # Iterate through a copy of the set to avoid issues while modifying
            # Filter rows for the current GUID
            guid_rows = df[df['GUID'] == guid]

            # Check if any of the rows have "ERROR", "exception", or similar in the "output" column
            has_error = guid_rows['output'].str.contains('ERROR', case=False, na=False) | \
                        guid_rows['output'].str.contains('Failed to satisfy prerequisites', case=False, na=False) | \
                        guid_rows['output'].str.contains('Failed getting command', case=False, na=False) | \
                        guid_rows['output'].str.contains('exception', case=False, na=False)

            # If any rows contain an error, remove the GUID from the set and add it to the error set
            if has_error.any():
                guids_with_errors.add(guid)
                guid_set.remove(guid)

        # Print all GUIDs that have errors
        if guids_with_errors:
            print(f"{len(guids_with_errors)} GUIDs with errors:", guids_with_errors)
        else:
            print("No GUIDs with errors found.")

        return guid_set

    except Exception as e:
        return f"An error occurred: {e}"

file_path = 'logs.csv'
filtered_guids = filter_guid_errors(file_path)

if isinstance(filtered_guids, set):
    print(f"{len(filtered_guids)} GUIDs without errors:", filtered_guids)
else:
    print(filtered_guids)


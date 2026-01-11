import pandas as pd
import random

# Load the dataset
file_path = 'dm2_final_flat_000000000000.csv'
try:
    df = pd.read_csv(file_path)
    print(f"Successfully loaded {file_path}. Total records: {len(df)}")
except FileNotFoundError:
    print(f"Error: File {file_path} not found.")
    exit(1)

# Select 300 random patients
# If there are fewer than 300 patients, take all of them.
n_samples = min(300, len(df))
sampled_df = df.sample(n=n_samples, random_state=42)

# Save to new CSV
output_file = 'patients_for_trial_screening.csv'
sampled_df.to_csv(output_file, index=False)

print(f"Successfully saved {n_samples} patients to {output_file}")

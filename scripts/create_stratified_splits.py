#!/usr/bin/env python3
"""
Create stratified train/validation/test splits for Alfa rating model training.

Stratification ensures balanced representation of:
- Game formats (9-ball, 8-ball, 10-ball)
- Table sizes (7ft, 8ft, 9ft)
- Combined format-size categories

Splits:
- Train: 60% (7,200 matches)
- Validation: 20% (2,400 matches)
- Test: 20% (2,400 matches)
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from sklearn.model_selection import train_test_split
from typing import Dict, Tuple, Any


def load_data(csv_path: str) -> pd.DataFrame:
    """Load the classified matches CSV."""
    print(f"Loading data from {csv_path}...")
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} records")
    return df


def create_stratification_column(df: pd.DataFrame) -> pd.DataFrame:
    """Create a stratification column combining format and table_size."""
    df['strat_group'] = df['format'] + '_' + df['table_size']
    return df


def analyze_distribution(df: pd.DataFrame, name: str) -> Dict[str, Any]:
    """Analyze the distribution of stratification groups."""
    print(f"\n=== Distribution Analysis: {name} ===")
    
    format_counts = df['format'].value_counts()
    table_counts = df['table_size'].value_counts()
    strat_counts = df['strat_group'].value_counts().sort_index()
    
    print(f"\nGame Formats ({len(format_counts)} unique):")
    for fmt, count in format_counts.items():
        pct = (count / len(df)) * 100
        print(f"  {fmt}: {count:,} ({pct:.2f}%)")
    
    print(f"\nTable Sizes ({len(table_counts)} unique):")
    for size, count in table_counts.items():
        pct = (count / len(df)) * 100
        print(f"  {size}: {count:,} ({pct:.2f}%)")
    
    print(f"\nStratification Groups ({len(strat_counts)} unique):")
    for group, count in strat_counts.items():
        pct = (count / len(df)) * 100
        print(f"  {group}: {count:,} ({pct:.2f}%)")
    
    return {
        'total_records': len(df),
        'formats': format_counts.to_dict(),
        'table_sizes': table_counts.to_dict(),
        'strat_groups': strat_counts.to_dict(),
        'format_percentages': {k: f"{(v/len(df))*100:.2f}%" for k, v in format_counts.items()},
        'table_size_percentages': {k: f"{(v/len(df))*100:.2f}%" for k, v in table_counts.items()},
    }


def perform_stratified_split(
    df: pd.DataFrame,
    train_size: float = 0.6,
    val_size: float = 0.2,
    test_size: float = 0.2,
    random_state: int = 42
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Perform stratified split into train/val/test.
    
    Using two-stage split:
    1. Split into train (60%) and temp (40%) stratified
    2. Split temp into val (50%) and test (50%) stratified
    """
    print("\nPerforming stratified split...")
    
    # First split: train vs. rest
    train_df, temp_df = train_test_split(
        df,
        train_size=train_size,
        test_size=(val_size + test_size),
        stratify=df['strat_group'],
        random_state=random_state
    )
    
    # Second split: val vs. test (equal split of remaining)
    val_df, test_df = train_test_split(
        temp_df,
        train_size=val_size / (val_size + test_size),
        test_size=test_size / (val_size + test_size),
        stratify=temp_df['strat_group'],
        random_state=random_state
    )
    
    print(f"Train set: {len(train_df):,} records ({len(train_df)/len(df)*100:.2f}%)")
    print(f"Validation set: {len(val_df):,} records ({len(val_df)/len(df)*100:.2f}%)")
    print(f"Test set: {len(test_df):,} records ({len(test_df)/len(df)*100:.2f}%)")
    
    return train_df, val_df, test_df


def save_splits(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    output_dir: str
) -> None:
    """Save split datasets to CSV files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"\nSaving splits to {output_dir}...")
    
    train_path = output_path / 'train_matches.csv'
    val_path = output_path / 'val_matches.csv'
    test_path = output_path / 'test_matches.csv'
    
    train_df.to_csv(train_path, index=False)
    val_df.to_csv(val_path, index=False)
    test_df.to_csv(test_path, index=False)
    
    print(f"  Saved {train_path}")
    print(f"  Saved {val_path}")
    print(f"  Saved {test_path}")


def generate_split_metadata(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    original_analysis: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate metadata about the splits."""
    metadata = {
        'total_records': len(train_df) + len(val_df) + len(test_df),
        'split_sizes': {
            'train': {
                'records': len(train_df),
                'percentage': f"{len(train_df)/(len(train_df)+len(val_df)+len(test_df))*100:.2f}%"
            },
            'validation': {
                'records': len(val_df),
                'percentage': f"{len(val_df)/(len(train_df)+len(val_df)+len(test_df))*100:.2f}%"
            },
            'test': {
                'records': len(test_df),
                'percentage': f"{len(test_df)/(len(train_df)+len(val_df)+len(test_df))*100:.2f}%"
            }
        },
        'stratification': {
            'base_column': 'format_table_size combination',
            'original': original_analysis
        },
        'split_distributions': {
            'train': analyze_split(train_df),
            'validation': analyze_split(val_df),
            'test': analyze_split(test_df)
        }
    }
    return metadata


def analyze_split(df: pd.DataFrame) -> Dict[str, Any]:
    """Analyze distribution within a split."""
    total = len(df)
    return {
        'total_records': total,
        'formats': {
            fmt: {
                'count': count,
                'percentage': f"{count/total*100:.2f}%"
            }
            for fmt, count in df['format'].value_counts().items()
        },
        'table_sizes': {
            size: {
                'count': count,
                'percentage': f"{count/total*100:.2f}%"
            }
            for size, count in df['table_size'].value_counts().items()
        },
        'strat_groups': {
            group: {
                'count': count,
                'percentage': f"{count/total*100:.2f}%"
            }
            for group, count in df['strat_group'].value_counts().sort_index().items()
        }
    }


def save_metadata(metadata: Dict[str, Any], output_dir: str) -> None:
    """Save metadata to JSON."""
    output_path = Path(output_dir)
    metadata_file = output_path / 'split_info.json'
    
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"  Saved {metadata_file}")


def verify_no_overlap(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame
) -> bool:
    """Verify that splits have no overlapping records."""
    print("\nVerifying no overlap between splits...")
    
    train_ids = set(train_df['match_id'])
    val_ids = set(val_df['match_id'])
    test_ids = set(test_df['match_id'])
    
    train_val_overlap = len(train_ids & val_ids)
    train_test_overlap = len(train_ids & test_ids)
    val_test_overlap = len(val_ids & test_ids)
    
    print(f"  Train-Val overlap: {train_val_overlap}")
    print(f"  Train-Test overlap: {train_test_overlap}")
    print(f"  Val-Test overlap: {val_test_overlap}")
    
    total_ids = len(train_ids | val_ids | test_ids)
    total_records = len(train_df) + len(val_df) + len(test_df)
    
    print(f"  Unique IDs: {total_ids}")
    print(f"  Total records: {total_records}")
    
    if train_val_overlap == 0 and train_test_overlap == 0 and val_test_overlap == 0:
        print("  ✓ No overlap detected")
        return True
    else:
        print("  ✗ Overlap detected!")
        return False


def print_sample_rows(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    n_samples: int = 3
) -> None:
    """Print sample rows from each split."""
    print(f"\n=== Sample Rows from Each Split ({n_samples} per split) ===\n")
    
    print("TRAIN SET SAMPLE:")
    print(train_df[['match_id', 'player_1_name', 'player_2_name', 'format', 'table_size', 'winner_id']].head(n_samples).to_string(index=False))
    
    print("\n\nVALIDATION SET SAMPLE:")
    print(val_df[['match_id', 'player_1_name', 'player_2_name', 'format', 'table_size', 'winner_id']].head(n_samples).to_string(index=False))
    
    print("\n\nTEST SET SAMPLE:")
    print(test_df[['match_id', 'player_1_name', 'player_2_name', 'format', 'table_size', 'winner_id']].head(n_samples).to_string(index=False))


def main():
    """Main execution."""
    # Paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    data_path = project_root / 'data' / 'alfa_matches_classified.csv'
    output_dir = project_root / 'data' / 'splits'
    
    # Load and prepare data
    df = load_data(str(data_path))
    df = create_stratification_column(df)
    
    # Analyze original distribution
    original_analysis = analyze_distribution(df, "ORIGINAL DATASET")
    
    # Perform stratified split
    train_df, val_df, test_df = perform_stratified_split(df)
    
    # Verify no overlap
    verify_no_overlap(train_df, val_df, test_df)
    
    # Save splits
    save_splits(train_df, val_df, test_df, str(output_dir))
    
    # Generate and save metadata
    metadata = generate_split_metadata(train_df, val_df, test_df, original_analysis)
    save_metadata(metadata, str(output_dir))
    
    # Print sample rows
    print_sample_rows(train_df, val_df, test_df, n_samples=3)
    
    # Print distribution verification
    print("\n" + "="*60)
    print("STRATIFICATION VERIFICATION")
    print("="*60)
    
    analyze_distribution(train_df, "TRAIN SET")
    analyze_distribution(val_df, "VALIDATION SET")
    analyze_distribution(test_df, "TEST SET")
    
    print("\n" + "="*60)
    print("SPLIT CREATION COMPLETE")
    print("="*60)
    print(f"\nOutput files saved to: {output_dir}")
    print(f"  - train_matches.csv ({len(train_df):,} records)")
    print(f"  - val_matches.csv ({len(val_df):,} records)")
    print(f"  - test_matches.csv ({len(test_df):,} records)")
    print(f"  - split_info.json (metadata)")


if __name__ == "__main__":
    main()

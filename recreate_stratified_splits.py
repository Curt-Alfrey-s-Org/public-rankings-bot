#!/usr/bin/env python3
"""
Recreate train/val/test splits with proper stratification across context variables.
This ensures each split has representative samples from all table sizes, formats, etc.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.model_selection import train_test_split

def create_stratified_splits(input_file='data/alfa_matches.csv', 
                             output_dir='data/splits',
                             train_size=0.6, val_size=0.2, test_size=0.2,
                             random_state=42):
    """
    Create stratified train/val/test splits.
    
    Args:
        train_size: Fraction for training (default 0.6)
        val_size: Fraction for validation (default 0.2)
        test_size: Fraction for testing (default 0.2)
    """
    
    # Load data
    df = pd.read_csv(input_file)
    print(f"✓ Loaded {len(df)} matches from {input_file}")
    
    # Create stratification key combining context variables
    df['strat_key'] = (df['table_size'].astype(str) + '_' + 
                       df['format'].astype(str) + '_' +
                       df['event_type'].astype(str))
    
    print(f"\nStratification Groups:")
    strat_counts = df['strat_key'].value_counts()
    print(strat_counts)
    
    # First split: train+val vs test
    train_val, test = train_test_split(
        df, 
        test_size=test_size, 
        random_state=random_state,
        stratify=df['strat_key']
    )
    
    # Second split: train vs val
    train_size_adj = train_size / (train_size + val_size)
    train, val = train_test_split(
        train_val,
        test_size=1-train_size_adj,
        random_state=random_state,
        stratify=train_val['strat_key']
    )
    
    # Remove stratification key
    train = train.drop('strat_key', axis=1)
    val = val.drop('strat_key', axis=1)
    test = test.drop('strat_key', axis=1)
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save splits
    train.to_csv(output_path / 'train_matches.csv', index=False)
    val.to_csv(output_path / 'val_matches.csv', index=False)
    test.to_csv(output_path / 'test_matches.csv', index=False)
    
    print(f"\n✓ Created stratified splits:")
    print(f"  Train: {len(train)} matches ({len(train)/len(df)*100:.1f}%)")
    print(f"  Val:   {len(val)} matches ({len(val)/len(df)*100:.1f}%)")
    print(f"  Test:  {len(test)} matches ({len(test)/len(df)*100:.1f}%)")
    
    # Verify stratification in each split
    print(f"\n✓ Stratification verification:")
    for split_name, split_df in [('Train', train), ('Val', val), ('Test', test)]:
        print(f"\n  {split_name}:")
        print(f"    Table sizes: {sorted(split_df['table_size'].unique())}")
        print(f"    Formats: {sorted(split_df['format'].unique())}")
        print(f"    Event types: {sorted(split_df['event_type'].unique())}")
    
    # Save split info
    split_info = {
        'train_size': len(train),
        'val_size': len(val),
        'test_size': len(test),
        'random_state': random_state,
        'stratification': 'table_size_format_event_type'
    }
    
    import json
    with open(output_path / 'split_info.json', 'w') as f:
        json.dump(split_info, f, indent=2)
    
    print(f"\n✓ Split info saved to {output_path}/split_info.json")

if __name__ == '__main__':
    create_stratified_splits()

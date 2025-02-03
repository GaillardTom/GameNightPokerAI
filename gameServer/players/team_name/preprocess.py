# TODO:// Add a helper function
"""Helper class"""
import numpy as np


#Suit (1- 4 ) representing (Hearts, Diamonds, Clubs , Spades)

# Card rank (1-13) representing (Ace, 2, 3, 4, 5, 6, 7, 8, 9, 10, Jack, Queen, King)

# Example of hand: 118,2,4,2,3,4,9,3,12,4,8,0
# This hand contains 5 cards with the following ranks and suits:
# 1. 4 of Diamond




# Helper function to add a column that counts the number of unique suits in each hand
def add_unique_count(df):
    """
    Adds a new column "unique_suit" to the given DataFrame, counting the number of unique suits present in each hand.
    This is useful for identifying flush hands, which will always have a unique suit count of 1.

    Args:
        df (pd.DataFrame): The DataFrame containing hand data with columns "S1", "S2", "S3", "S4", and "S5" for suits.

    Returns:
        pd.DataFrame: The updated DataFrame with an additional column "unique_suit".
    """
    tmp_suit = df[["S1", "S2", "S3", "S4", "S5"]]  # Extract suit columns
    df["unique_suit"] = tmp_suit.apply(lambda s: len(np.unique(s)), axis=1)  # Count unique suits in each hand
    return df

    
    

def add_pair_count(df):
    """
    Adds a new column "pair_count" to the given DataFrame, counting the number of pairs present in each hand.
    This is useful for identifying hands with pairs, which will have a pair count greater than 0.

    Args:
        df (pd.DataFrame): The DataFrame containing hand data with columns "C1", "C2", "C3", "C4", and "C5" for card ranks.

    Returns:
        pd.DataFrame: The updated DataFrame with an additional column "pair_count".
    """
    tmp_card = df[["C1", "C2", "C3", "C4", "C5"]]  # Extract card rank columns instead of suit
    df["pair_count"] = tmp_card.apply(lambda s: len(s) - len(np.unique(s)), axis=1)  # Count pairs in each hand
    return df 

def add_three_of_a_kind_count(df):
    """
    Adds a new column "three_of_a_kind_count" to the given DataFrame, counting the number of three-of-a-kind present in each hand.
    This is useful for identifying hands with three-of-a-kind, which will have a three-of-a-kind count greater than 0.

    Args:
        df (pd.DataFrame): The DataFrame containing hand data with columns "C1", "C2", "C3", "C4", and "C5" for card ranks.

    Returns:
        pd.DataFrame: The updated DataFrame with an additional column "three_of_a_kind_count".
    """
    tmp_card = df[["C1", "C2", "C3", "C4", "C5"]]  # Extract card rank columns
    #df["three_of_a_kind_count"] = tmp_card.apply(lambda s: len(s) - len(np.unique(s)), axis=1)  # Count three-of-a-kind in each hand
    df["three_of_a_kind_count"] = tmp_card.apply(lambda s: sum([list(s).count(x) == 3 for x in set(s)]), axis=1)  # Count three-of-a-kind in each hand
    return df


def add_straight_count(df):
    """
    Adds a new column "straight_count" to the given DataFrame, counting the number of straights present in each hand.
    This is useful for identifying hands with straights, which will have a straight count greater than 0.

    Args:
        df (pd.DataFrame): The DataFrame containing hand data with columns "C1", "C2", "C3", "C4", and "C5" for card ranks.

    Returns:
        pd.DataFrame: The updated DataFrame with an additional column "straight_count".
    """
    tmp_card = df[["C1", "C2", "C3", "C4", "C5"]]  # Extract card rank columns
    df["straight_count"] = tmp_card.apply(lambda s: 1 if sorted(s) == list(range(min(s), min(s) + 5)) else 0, axis=1)  # 1 if there's a straight, 0 if not for all hands in df

    return df
# Main function to preprocess the data for further analysis and classification
def pre_process_data(data):
    """
    Preprocesses the hand data to prepare it for relationship calculations:
    1. Sorts card ranks and suits to standardize the order for comparison.
    2. Reorders columns to group suits and cards for intuitive analysis.
    3. Adds the "unique_suit" column using the helper function to detect flushes.

    Args:
        data (pd.DataFrame): The DataFrame containing hand data with card rank columns ("C1", ..., "C5")
                            and suit columns ("S1", ..., "S5").

    Returns:
        pd.DataFrame: The preprocessed DataFrame with sorted cards and suits, reordered columns, and the "unique_suit" column added.
    """
    df = data.copy()  # Create a copy to avoid modifying the original data
    cards = df[["C1", "C2", "C3", "C4", "C5"]]  # Extract card rank columns
    suits = df[["S1", "S2", "S3", "S4", "S5"]]  # Extract suit columns
    cards.values.sort()  # Sort card ranks in ascending order for easier comparison
    suits.values.sort()  # Sort suits in ascending order
    df[["C1", "C2", "C3", "C4", "C5"]] = cards  # Update the DataFrame with sorted card ranks
    df[["S1", "S2", "S3", "S4", "S5"]] = suits  # Update the DataFrame with sorted suits
    df = df[["S1", "C1", "S2", "C2", "S3", "C3", "S4", "C4", "S5", "C5"]]  # Reorder columns for better readability


    #Call the helpers functinos to add the columns
    df = add_unique_count(df)  # Add the unique suit count column for flush detection
    df = add_pair_count(df)  # Add the pair count column for pair detection 
    df = add_three_of_a_kind_count(df) # Add the three of a kind count column for three of a kind detection 
    df = add_straight_count(df)  # Add the straight count column for straight detection

    return df



if __name__ == "__main__": 
    try: 
        print("Preprocess.py with straight, pair and three of a kind") 
    except KeyboardInterrupt as e: 
        print("User interrupted the program")
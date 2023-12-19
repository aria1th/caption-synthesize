# calls gemini API with multiple API keys
import argparse
from futures import ProcessPoolExecutor

def split_list(l, n):
    """
    Split the list into n chunks.
    """
    for i in range(0, len(l), n):
        yield l[i:i + n]
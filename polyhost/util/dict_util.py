
def split_dict(input_dict, max_keys=12):
    """ Split a dict by a given numbers of entries """
    # Convert the dictionary items into a list
    items = list(input_dict.items())
    max_keys = min(max_keys, len(items))
    if max_keys==0:
        return []

    # Split the items into chunks of `max_keys`
    chunks = [items[i:i + max_keys] for i in range(0, len(items), max_keys)]
    
    # Convert each chunk back into a dictionary
    dicts = [dict(chunk) for chunk in chunks]
    
    return dicts

def split_by_n_chars(text, n):
    """ Split a text by the given number of characters """
    return [text[i : i + n] for i in range(0, len(text), n)]

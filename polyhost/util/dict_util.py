
def split_dict(input_dict, max_keys=12):
    # Convert the dictionary items into a list
    items = list(input_dict.items())
    
    # Split the items into chunks of `max_keys`
    chunks = [items[i:i + max_keys] for i in range(0, len(items), max_keys)]
    
    # Convert each chunk back into a dictionary
    dicts = [dict(chunk) for chunk in chunks]
    
    return dicts

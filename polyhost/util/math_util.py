import math


def natural_divisors(n):
    """Find all natural divisors of a given positive number, returns a sorted array"""
    if n == 0:
        return []
    if n == 1:
        return [1]
    arr = [1]
    for i in range(2, int(math.sqrt(n)) + 1):
        if n % i == 0:
            j = int(n / i)
            arr.extend([i])
            if j != i:
                arr.extend([j])
    arr.extend([n])
    arr.sort()
    return arr


def find_nearest(n, arr):
    """Find the nearest number not over the specified for a given, sorted array"""
    elem = arr[0]
    for i in arr:
        if i > n:
            break
        if i > elem:
            elem = i
    return elem

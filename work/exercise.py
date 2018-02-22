#!/usr/bin/python


def word_break(s):
    dictionary = set(['ax', 'be', 'ab'])
    # print("hello {}!".format(parameter))

    def breakup(word):
        size = len(word)
        if size == 0:
            return True

        for i in range(1, size + 1):
            if word[0:i] in dictionary and breakup(word[i:]):
                print word[0:i]
                return True
        return False
    return breakup(s)


def max_diff(arr):
    max_diff = -1
    pos = None
    l = len(arr)
    for i in range(l):
        for j in range(l - 1, i, -1):
            print i, j
            if arr[j] > arr[i] and max_diff < j - i:
                max_diff = j - i
                pos = (j,i)
    print pos
    return max_diff


def bin_search(arr, x):
    min = 0
    max = len(arr) - 1
    while min <= max:
        guess = (min + max) / 2
        print guess, min, max
        if arr[guess] == x:
            return guess
        elif arr[guess] < x:
            min = guess + 1
        else:
            max = guess - 1


def power_set(arr):
    n = len(arr) 
    
    for i in range(2 ** n):
        print '{',
        for j in range(n):
            if i & (1 << j):
                print arr[j],
        print '}'


def flood_fill(mat, x, y, c):
    prevC = mat[x][y]
    M = len(mat)
    N = len(mat[0])

    def flood_fill2(mat, x, y, p, c):
        if x < 0 or x >= M or y < 0 or y >= N:
            return
        if mat[x][y] != p:
            return
        mat[x][y] = c

        flood_fill2(mat, x + 1, y, p, c)
        flood_fill2(mat, x, y + 1, p, c)
        flood_fill2(mat, x - 1, y, p, c)
        flood_fill2(mat, x, y - 1, p, c)
    
    flood_fill2(mat, x, y, prevC, c)
    return mat


def coins(v):
    types = [1, 5, 10, 25, 50, 100]
    values = []

    for i in reversed(range(len(types))):
        while v >= types[i]:
            v -= types[i]
            values.append(types[i])
    return values


def egg_drop(eggs, floors):
    if floors <= 1:
        return floors
    if eggs == 1:
        return floors
    m = 999
    for i in range(1, floors + 1):
        res = max(egg_drop(eggs - 1, i - 1), egg_drop(eggs, floors - i))
        if res < m:
            m = res
    return m + 1

def egg_drop2(n, k):
    # A 2D table where entery eggFloor[i][j] will represent minimum
    # number of trials needed for i eggs and j floors.
    eggFloor = [[0 for x in range(k+1)] for x in range(n+1)]
 
    # We need one trial for one floor and0 trials for 0 floors
    for i in range(1, n+1):
        eggFloor[i][1] = 1
        eggFloor[i][0] = 0
 
    # We always need j trials for one egg and j floors.
    for j in range(1, k+1):
        eggFloor[1][j] = j
 
    # Fill rest of the entries in table using optimal substructure
    # property
    for i in range(2, n+1):
        for j in range(2, k+1):
            eggFloor[i][j] = 999
            for x in range(1, j+1):
                res = 1 + max(eggFloor[i-1][x-1], eggFloor[i][j-x])
                if res < eggFloor[i][j]:
                    eggFloor[i][j] = res
 
    # eggFloor[n][k] holds the result
    return eggFloor[n][k]


def bubble_sort(arr):
    n = len(arr)
    for i in range(n - 1):
        for j in range(n - i - 1):
            if arr[j] > arr[j + 1]:
                tmp = arr[j + 1]
                arr[j + 1] = arr[j]
                arr[j] = tmp
    return arr


def substr(s1, s2):
    i, j = 0, 0
    matching_count = 0

    if len(s2) > len(s1):
        return False

    while i < len(s1) and j < len(s2):
        if s1[i] == s2[j]:
            matching_count += 1
            j += 1
        else:
            matching_count = 0
            j = 0
        i += 1
    
    return matching_count == len(s2)


if __name__ == '__main__':
    #print(word_break('abbe'))
    #print(max_diff([6, 5, 4, 3, 2, 1]))
    #print(bin_search([1,2,6,8,9,10,11], 0))
    #print(power_set([1,3,4,2]))
    #print(flood_fill([[1,1,1],[1,2,2],[3,3,1]], 0, 0, 0))
    #print(coins(123))
    #print egg_drop2(10, 100)
    #print(bubble_sort([8, 4, 2, 5, 1, 7, 3]))
    print substr('abac', 'caaaa')

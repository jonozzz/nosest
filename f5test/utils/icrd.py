'''
Created on May 20, 2016

Contains helpers for encoding/decoding information to/from icrd.

@author: langer
'''

def get_full_path(obj):
    if obj.get('subPath') is None:
        full_path = '/'.join(['', obj.partition, obj.name])
    else:
        full_path = '/'.join(['', obj.partition, obj.subPath, obj.name])
    return full_path


def split_full_path(full_path):
    path_chunks = full_path.split('/')
    partition = path_chunks[1]
    name = path_chunks[-1]
    if len(path_chunks) > 3:
        sub_path = '/'.join(path_chunks[2:-1])
    else:
        sub_path = None

    return partition, sub_path, name
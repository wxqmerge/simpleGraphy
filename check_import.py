import sys
sys.path.insert(0, 'D:/xampp/htdocs/simpleGraphy')
from generate_gallery import get_subdirectory_list

# Test with the www_misc directory
result = get_subdirectory_list('D:/xampp/htdocs/www_misc')
print(f"subdirs_list: {len(result)} items")
print(f"First 5: {result[:5]}")

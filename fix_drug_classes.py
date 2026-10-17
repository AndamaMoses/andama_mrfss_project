"""Fix CSS class names in drug catalogue JS section."""
path = 'templates/index.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Simple targeted replacements within the drug section only
# These class names only appear in the drug JS we just added
replacements = [
    ('class="pill-badge"', 'class="pill-ok"'),
    ("class='pill-badge'", "class='pill-ok'"),
    ('class="low-badge"', 'class="pill-low"'),
    ("class='low-badge'", "class='pill-low'"),
    ('class="btn-edit"', 'class="btn-edit-sm"'),
    ('class="btn-red"', 'class="btn-red-sm"'),
]

for old, new in replacements:
    if old in content:
        count = content.count(old)
        content = content.replace(old, new)
        print(f'  Replaced {count}x: {old!r} -> {new!r}')
    else:
        print(f'  Not found: {old!r}')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Done.')

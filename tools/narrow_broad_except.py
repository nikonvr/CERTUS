#!/usr/bin/env python
"""
Utility to analyze and narrow broad except patterns.

Usage: python tools/narrow_broad_except.py --analyze [--file FILENAME]
"""

import re
from pathlib import Path
from typing import NamedTuple


class BroadExceptMatch(NamedTuple):
    """Info about a broad except location."""
    filename: str
    line_number: int
    line_text: str
    context_before: str
    context_after: str
    suggestion: str


def find_broad_except_patterns(
    file_path: Path,
    context_lines: int = 10,
) -> list[BroadExceptMatch]:
    """Find all broad except Exception/BaseException patterns with context."""
    
    matches = []
    content = file_path.read_text(encoding='utf-8', errors='ignore')
    lines = content.split('\n')
    
    broad_pattern = re.compile(r'^\s*except\s+(Exception|BaseException)\s*:')
    
    for i, line in enumerate(lines):
        if broad_pattern.search(line):
            start = max(0, i - context_lines)
            end = min(len(lines), i + context_lines + 1)
            
            context_before = '\n'.join(lines[start:i])
            context_after = '\n'.join(lines[i+1:end])
            
            # Analyze what should be caught
            suggestion = infer_exception_type(context_after, lines, i)
            
            matches.append(BroadExceptMatch(
                filename=str(file_path),
                line_number=i + 1,  # 1-indexed
                line_text=line,
                context_before=context_before,
                context_after=context_after,
                suggestion=suggestion,
            ))
    
    return matches


def infer_exception_type(context_after: str, lines: list[str], line_idx: int) -> str:
    "Infer what specific exception types should be caught."
    
    # Look for common patterns
    
    context = '\n'.join(lines[max(0, line_idx-5):min(len(lines), line_idx+15)])
    
    if any(word in context for word in ['open(', 'read_text', 'write_text', '.json', 'dump']):
        return 'IOError, OSError'
    elif any(word in context for word in ['import ', '__import__']):
        return 'ImportError, ModuleNotFoundError'
    elif any(word in context for word in ['[', 'get(', '.key']):
        return 'KeyError, TypeError, AttributeError'
    elif any(word in context for word in ['.fit(', 'svc.', 'service']):
        return 'Exception  # Service calls - needs analysis'
    else:
        return 'Exception  # Context unclear - needs manual review'


def main():
    """Run analysis."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze broad except patterns')
    parser.add_argument('--analyze', action='store_true', help='Analyze patterns')
    parser.add_argument('--file', type=str, help='Specific file to analyze')
    
    args = parser.parse_args()
    
    if not args.analyze:
        parser.print_help()
        return
    
    root = Path('.')
    py_files = [f for f in root.glob('*.py') if f.is_file()]
    
    if args.file:
        py_files = [Path(args.file)]
    
    all_matches = []
    for py_file in sorted(py_files):
        matches = find_broad_except_patterns(py_file)
        all_matches.extend(matches)
    
    if not all_matches:
        print("✓ No broad except patterns found!")
        return
    
    print(f"\n{'='*80}")
    print(f"Found {len(all_matches)} broad except patterns")
    print(f"{'='*80}\n")
    
    for match in all_matches:
        print(f"\n{match.filename}:{match.line_number}")
        print(f"  Line: {match.line_text.strip()}")
        print(f"  Suggestion: {match.suggestion}")
        print(f"  Context (next 5 lines):\n{match.context_after[:200]}...")


if __name__ == '__main__':
    main()

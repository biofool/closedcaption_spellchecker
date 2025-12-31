#!/usr/bin/env python3
"""
Caption Diff Mapper - Build terminology mappings from spell-checked captions
Author: Claude
Description: Compares original caption JSON with spell-checked version to 
             automatically build and update terminology mapping files.
"""

import os
import sys
import json
import re
import logging
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import Counter
from difflib import SequenceMatcher, ndiff
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================
CACHE_DIR = Path(os.getenv("CACHE_DIR", ".cache"))
OUTPUT_DIR = CACHE_DIR / "output"
LOG_DIR = CACHE_DIR / "logs"

# Terminology mapping file from .env
MAPPING_FILE = Path(os.getenv("TERMINOLOGY_MAPPING_FILE", ".cache/terminology_mapping.json"))

# Create directories
for directory in [CACHE_DIR, OUTPUT_DIR, LOG_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# ============================================================================
# LOGGING
# ============================================================================
LOG_FILE = LOG_DIR / f"diff_mapper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logger = logging.getLogger("CaptionDiffMapper")
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s | %(levelname)-8s | %(funcName)-25s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))

logger.addHandler(file_handler)
logger.addHandler(console_handler)


# ============================================================================
# DATA STRUCTURES
# ============================================================================
@dataclass
class DiffResult:
    """A single difference found between original and corrected text"""
    original: str
    corrected: str
    count: int = 1
    contexts: List[str] = field(default_factory=list)
    
    def add_context(self, context: str):
        if len(self.contexts) < 5:  # Keep up to 5 examples
            self.contexts.append(context)


@dataclass
class MappingReport:
    """Summary of mapping generation"""
    original_file: str
    corrected_file: str
    generated_at: str
    total_differences: int
    unique_mappings: int
    new_mappings: int
    existing_mappings_updated: int
    mappings: Dict[str, str]


# ============================================================================
# DIFF ENGINE
# ============================================================================
class CaptionDiffMapper:
    """Compares captions and builds terminology mappings"""
    
    def __init__(self, mapping_file: Path = MAPPING_FILE):
        self.mapping_file = mapping_file
        self.existing_mappings: Dict[str, str] = {}
        self.load_existing_mappings()
    
    def load_existing_mappings(self) -> Dict[str, str]:
        """Load existing terminology mappings if they exist"""
        if not self.mapping_file.exists():
            logger.info(f"No existing mapping file found at {self.mapping_file}")
            return {}
        
        try:
            with open(self.mapping_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, dict):
                if 'mappings' in data:
                    self.existing_mappings = data['mappings']
                else:
                    self.existing_mappings = data
            
            logger.info(f"Loaded {len(self.existing_mappings)} existing mappings")
            return self.existing_mappings
            
        except Exception as e:
            logger.error(f"Error loading mappings: {e}")
            return {}
    
    def load_caption_json(self, filepath: Path) -> Dict:
        """Load a caption batch JSON file"""
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def extract_words(self, text: str) -> List[str]:
        """Extract words from text, preserving order"""
        # Split on whitespace and punctuation but keep words intact
        words = re.findall(r"[A-Za-z'-]+", text)
        return words
    
    def find_word_differences(self, original: str, corrected: str) -> List[Tuple[str, str]]:
        """Find word-level differences between two texts"""
        differences = []
        
        orig_words = self.extract_words(original)
        corr_words = self.extract_words(corrected)
        
        # Use sequence matcher to align words
        matcher = SequenceMatcher(None, orig_words, corr_words)
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                # Words were changed
                orig_chunk = ' '.join(orig_words[i1:i2])
                corr_chunk = ' '.join(corr_words[j1:j2])
                
                # Only add if they're different (case-insensitive check for real changes)
                if orig_chunk.lower() != corr_chunk.lower():
                    differences.append((orig_chunk, corr_chunk))
                    
            elif tag == 'delete':
                # Words were removed (might be corrections of repeated/wrong words)
                deleted = ' '.join(orig_words[i1:i2])
                if deleted.strip():
                    logger.debug(f"Deleted: '{deleted}'")
                    
            elif tag == 'insert':
                # Words were added
                inserted = ' '.join(corr_words[j1:j2])
                if inserted.strip():
                    logger.debug(f"Inserted: '{inserted}'")
        
        return differences
    
    def find_phrase_differences(self, original: str, corrected: str, 
                                 min_phrase_len: int = 2, 
                                 max_phrase_len: int = 4) -> List[Tuple[str, str]]:
        """Find multi-word phrase differences (for terms like 'Tai no henko')"""
        differences = []
        
        orig_words = original.split()
        corr_words = corrected.split()
        
        # Use sequence matcher
        matcher = SequenceMatcher(None, orig_words, corr_words)
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                orig_len = i2 - i1
                corr_len = j2 - j1
                
                # Check for multi-word phrases
                if min_phrase_len <= orig_len <= max_phrase_len or \
                   min_phrase_len <= corr_len <= max_phrase_len:
                    orig_phrase = ' '.join(orig_words[i1:i2])
                    corr_phrase = ' '.join(corr_words[j1:j2])
                    
                    # Clean up phrases
                    orig_phrase = re.sub(r'[^\w\s\'-]', '', orig_phrase).strip()
                    corr_phrase = re.sub(r'[^\w\s\'-]', '', corr_phrase).strip()
                    
                    if orig_phrase and corr_phrase and orig_phrase != corr_phrase:
                        differences.append((orig_phrase, corr_phrase))
        
        return differences
    
    def compare_segment_texts(self, original: str, corrected: str) -> Dict[str, DiffResult]:
        """Compare two text strings and find all differences"""
        results: Dict[str, DiffResult] = {}
        
        # Find single-word differences
        word_diffs = self.find_word_differences(original, corrected)
        for orig, corr in word_diffs:
            key = orig.lower()
            if key in results:
                results[key].count += 1
            else:
                results[key] = DiffResult(original=orig, corrected=corr)
            
            # Add context (surrounding words)
            idx = original.lower().find(orig.lower())
            if idx >= 0:
                start = max(0, idx - 30)
                end = min(len(original), idx + len(orig) + 30)
                context = original[start:end]
                results[key].add_context(f"...{context}...")
        
        # Find phrase differences
        phrase_diffs = self.find_phrase_differences(original, corrected)
        for orig, corr in phrase_diffs:
            key = orig.lower()
            if key in results:
                results[key].count += 1
            else:
                results[key] = DiffResult(original=orig, corrected=corr)
        
        return results
    
    def compare_batches(self, original_data: Dict, corrected_data: Dict) -> Dict[str, DiffResult]:
        """Compare two caption batch files"""
        all_diffs: Dict[str, DiffResult] = {}
        
        # Build lookup for corrected videos by ID
        corrected_lookup = {
            v['video_id']: v for v in corrected_data.get('videos', [])
        }
        
        for orig_video in original_data.get('videos', []):
            video_id = orig_video['video_id']
            
            if video_id not in corrected_lookup:
                logger.warning(f"Video {video_id} not found in corrected file")
                continue
            
            corr_video = corrected_lookup[video_id]
            
            logger.debug(f"Comparing: {orig_video['title'][:40]}...")
            
            # Compare full_text fields (primary comparison)
            orig_text = orig_video.get('full_text', '')
            corr_text = corr_video.get('full_text', '')
            
            if orig_text and corr_text:
                diffs = self.compare_segment_texts(orig_text, corr_text)
                
                for key, diff in diffs.items():
                    if key in all_diffs:
                        all_diffs[key].count += diff.count
                        all_diffs[key].contexts.extend(diff.contexts[:2])
                    else:
                        all_diffs[key] = diff
            
            # Also compare individual segments for more precise matching
            orig_segments = orig_video.get('segments', [])
            corr_segments = corr_video.get('segments', [])
            
            # Match segments by timestamp
            corr_seg_lookup = {
                (s['start'], s['end']): s for s in corr_segments
            }
            
            for orig_seg in orig_segments:
                key = (orig_seg['start'], orig_seg['end'])
                if key in corr_seg_lookup:
                    corr_seg = corr_seg_lookup[key]
                    seg_diffs = self.compare_segment_texts(
                        orig_seg['text'], 
                        corr_seg['text']
                    )
                    
                    for dk, dv in seg_diffs.items():
                        if dk in all_diffs:
                            all_diffs[dk].count += dv.count
                        else:
                            all_diffs[dk] = dv
        
        return all_diffs
    
    def generate_mappings(self, diffs: Dict[str, DiffResult], 
                          min_count: int = 1) -> Dict[str, str]:
        """Generate terminology mappings from differences"""
        mappings = {}
        
        for key, diff in diffs.items():
            if diff.count >= min_count:
                # Use the original case from first occurrence
                mappings[diff.original] = diff.corrected
                logger.debug(f"Mapping: '{diff.original}' -> '{diff.corrected}' (count: {diff.count})")
        
        return mappings
    
    def merge_mappings(self, new_mappings: Dict[str, str]) -> Tuple[Dict[str, str], int, int]:
        """Merge new mappings with existing ones"""
        merged = dict(self.existing_mappings)
        new_count = 0
        updated_count = 0
        
        for orig, corr in new_mappings.items():
            orig_lower = orig.lower()
            
            # Check if this mapping already exists (case-insensitive)
            existing_key = None
            for k in merged.keys():
                if k.lower() == orig_lower:
                    existing_key = k
                    break
            
            if existing_key:
                if merged[existing_key] != corr:
                    logger.info(f"Updating mapping: '{existing_key}' -> '{corr}' (was: '{merged[existing_key]}')")
                    merged[existing_key] = corr
                    updated_count += 1
            else:
                merged[orig] = corr
                new_count += 1
                logger.info(f"New mapping: '{orig}' -> '{corr}'")
        
        return merged, new_count, updated_count
    
    def save_mappings(self, mappings: Dict[str, str], 
                      output_file: Optional[Path] = None) -> Path:
        """Save mappings to JSON file"""
        if output_file is None:
            output_file = self.mapping_file
        
        # Create structured output
        data = {
            'version': '1.0',
            'updated_at': datetime.now().isoformat(),
            'total_mappings': len(mappings),
            'description': 'Aikido terminology corrections for YouTube auto-captions',
            'mappings': mappings
        }
        
        # Ensure parent directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)
        
        logger.info(f"Saved {len(mappings)} mappings to {output_file}")
        return output_file
    
    def generate_report(self, original_file: Path, corrected_file: Path,
                        diffs: Dict[str, DiffResult], 
                        mappings: Dict[str, str],
                        new_count: int, updated_count: int) -> MappingReport:
        """Generate a summary report"""
        return MappingReport(
            original_file=str(original_file),
            corrected_file=str(corrected_file),
            generated_at=datetime.now().isoformat(),
            total_differences=sum(d.count for d in diffs.values()),
            unique_mappings=len(mappings),
            new_mappings=new_count,
            existing_mappings_updated=updated_count,
            mappings=mappings
        )


# ============================================================================
# INTERACTIVE MODE
# ============================================================================
class InteractiveMapper:
    """Interactive review of detected differences"""
    
    def __init__(self, mapper: CaptionDiffMapper):
        self.mapper = mapper
    
    def review_diffs(self, diffs: Dict[str, DiffResult]) -> Dict[str, str]:
        """Interactively review differences and confirm mappings"""
        confirmed_mappings = {}
        
        print(f"\n{'='*60}")
        print("INTERACTIVE MAPPING REVIEW")
        print(f"{'='*60}")
        print(f"Found {len(diffs)} unique differences to review")
        print("Commands: [y]es, [n]o, [e]dit, [s]kip all, [q]uit\n")
        
        items = sorted(diffs.items(), key=lambda x: x[1].count, reverse=True)
        
        for i, (key, diff) in enumerate(items, 1):
            print(f"\n[{i}/{len(items)}] Found {diff.count}x:")
            print(f"  Original:  '{diff.original}'")
            print(f"  Corrected: '{diff.corrected}'")
            
            if diff.contexts:
                print(f"  Context:   {diff.contexts[0][:60]}...")
            
            while True:
                response = input("\n  Add mapping? [y/n/e/s/q]: ").strip().lower()
                
                if response == 'y':
                    confirmed_mappings[diff.original] = diff.corrected
                    print(f"  ✅ Added: '{diff.original}' -> '{diff.corrected}'")
                    break
                elif response == 'n':
                    print("  ⏭️  Skipped")
                    break
                elif response == 'e':
                    new_orig = input(f"  Original [{diff.original}]: ").strip()
                    new_corr = input(f"  Corrected [{diff.corrected}]: ").strip()
                    if new_orig or new_corr:
                        orig = new_orig if new_orig else diff.original
                        corr = new_corr if new_corr else diff.corrected
                        confirmed_mappings[orig] = corr
                        print(f"  ✅ Added: '{orig}' -> '{corr}'")
                    break
                elif response == 's':
                    print("\n⏭️  Skipping remaining differences...")
                    return confirmed_mappings
                elif response == 'q':
                    print("\n🛑 Quitting review...")
                    return confirmed_mappings
                else:
                    print("  Invalid input. Use y/n/e/s/q")
        
        return confirmed_mappings


# ============================================================================
# CLI INTERFACE
# ============================================================================
def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Build terminology mappings by comparing original and spell-checked captions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compare files and generate mappings automatically
  python caption_diff_mapper.py original.json corrected.json
  
  # Interactive mode - review each difference
  python caption_diff_mapper.py original.json corrected.json --interactive
  
  # Specify custom output mapping file
  python caption_diff_mapper.py original.json corrected.json -o my_mappings.json
  
  # Only include terms that appear multiple times
  python caption_diff_mapper.py original.json corrected.json --min-count 2
  
  # View current mappings
  python caption_diff_mapper.py --view

Workflow:
  1. Run caption_downloader.py to generate batch JSON files
  2. Copy the JSON and manually correct the 'full_text' fields
  3. Run this tool to diff the files and build terminology mappings
  4. Mappings are automatically used by caption_downloader.py on future runs

Environment Variables:
  TERMINOLOGY_MAPPING_FILE - Path to terminology mapping JSON (default: .cache/terminology_mapping.json)
        """
    )
    
    parser.add_argument('original', nargs='?', help='Original caption JSON file')
    parser.add_argument('corrected', nargs='?', help='Spell-checked caption JSON file')
    
    parser.add_argument('--output', '-o', help='Output mapping file (default: from .env or .cache/terminology_mapping.json)')
    parser.add_argument('--interactive', '-i', action='store_true',
                       help='Interactively review each difference')
    parser.add_argument('--min-count', '-m', type=int, default=1,
                       help='Minimum occurrence count for mappings (default: 1)')
    parser.add_argument('--view', '-v', action='store_true',
                       help='View current terminology mappings')
    parser.add_argument('--debug', '-d', action='store_true',
                       help='Enable debug output')
    
    args = parser.parse_args()
    
    if args.debug:
        console_handler.setLevel(logging.DEBUG)
    
    # Determine mapping file
    output_file = Path(args.output) if args.output else MAPPING_FILE
    
    # Initialize mapper
    mapper = CaptionDiffMapper(output_file)
    
    # View mode
    if args.view:
        print(f"\n📋 Terminology Mappings from: {output_file}")
        print(f"{'='*60}")
        
        if not mapper.existing_mappings:
            print("No mappings found.")
        else:
            print(f"Total mappings: {len(mapper.existing_mappings)}\n")
            
            # Sort alphabetically
            for orig, corr in sorted(mapper.existing_mappings.items()):
                print(f"  '{orig}' → '{corr}'")
        
        return
    
    # Check required arguments for diff mode
    if not args.original or not args.corrected:
        parser.print_help()
        print("\n❌ Error: Both original and corrected files are required")
        sys.exit(1)
    
    original_path = Path(args.original)
    corrected_path = Path(args.corrected)
    
    if not original_path.exists():
        print(f"❌ Error: Original file not found: {original_path}")
        sys.exit(1)
    
    if not corrected_path.exists():
        print(f"❌ Error: Corrected file not found: {corrected_path}")
        sys.exit(1)
    
    # Load files
    print(f"\n📂 Loading files...")
    print(f"   Original:  {original_path}")
    print(f"   Corrected: {corrected_path}")
    
    try:
        original_data = mapper.load_caption_json(original_path)
        corrected_data = mapper.load_caption_json(corrected_path)
    except Exception as e:
        print(f"❌ Error loading files: {e}")
        sys.exit(1)
    
    # Compare
    print(f"\n🔍 Comparing captions...")
    diffs = mapper.compare_batches(original_data, corrected_data)
    
    if not diffs:
        print("✅ No differences found!")
        return
    
    print(f"   Found {len(diffs)} unique differences")
    
    # Interactive or automatic
    if args.interactive:
        interactive = InteractiveMapper(mapper)
        new_mappings = interactive.review_diffs(diffs)
    else:
        new_mappings = mapper.generate_mappings(diffs, min_count=args.min_count)
        
        # Show preview
        print(f"\n📋 Generated mappings:")
        for orig, corr in sorted(new_mappings.items()):
            count = diffs.get(orig.lower(), DiffResult(orig, corr)).count
            print(f"   '{orig}' → '{corr}' ({count}x)")
    
    if not new_mappings:
        print("\n⚠️  No mappings to add")
        return
    
    # Merge with existing
    print(f"\n🔄 Merging with existing mappings...")
    merged, new_count, updated_count = mapper.merge_mappings(new_mappings)
    
    # Save
    saved_path = mapper.save_mappings(merged, output_file)
    
    # Report
    print(f"\n{'='*60}")
    print("📊 SUMMARY")
    print(f"{'='*60}")
    print(f"New mappings added:     {new_count}")
    print(f"Existing updated:       {updated_count}")
    print(f"Total mappings now:     {len(merged)}")
    print(f"Saved to:               {saved_path}")
    print(f"\n✅ Done! Mappings will be applied on next caption_downloader.py run")


if __name__ == "__main__":
    main()

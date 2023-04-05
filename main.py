import sys
from re import sub
from pathlib import Path
from shutil import unpack_archive, ReadError
from hashlib import md5

FOLDERS = {
           "images":   ('JPEG', 'PNG', 'JPG', 'SVG'),
           "video":    ('AVI', 'MP4', 'MOV', 'MKV'),
           "documents":('DOC', 'DOCX', 'TXT', 'PDF', 'XLSX', 'PPTX'),
           "audio":    ('MP3', 'OGG', 'WAV', 'AMR'),
           "archives": ('ZIP', 'GZ', 'TAR')
          }

CYR = "абвгдеёжзийклмнопрстуфхцчшщъыьэюяєіїґ"
TRN = ("a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "j", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u",
       "f", "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya", "je", "i", "ji", "g")
trn_dict = {}
for c, l in zip(CYR, TRN):
    trn_dict[ord(c)] = l
    trn_dict[ord(c.upper())] = l.upper()

#list of archives to unpack
archives = []
#counters
total = {}
other = 0
deleted = 0
duplicate = [0, 0]

def normalize(s: str) -> str:
    global trn_dict
    return sub(r'\W', '_', s.translate(trn_dict))

def plural(n: int):
    return n, " was" if n == 1 else "s were"

def calc_hash(f: Path) -> str:
    BUF_SIZE = 128 * 1024
    md = md5()
    if f.is_file():
        with open(f, 'rb') as x:
            while True:
                data = x.read(BUF_SIZE)
                if not data:
                    break
                md.update(data)
    return md.hexdigest()

def process_file(f: Path, target: str):
    global total, duplicate, archives, pth
    fname = normalize(f.stem)
    arc_folder = pth / target 
    new_file = arc_folder / (fname + f.suffix)
    #duplicate name check (extended for archives - to prevent more than one archive being unpacked into the same folder)
    if new_file.exists() or target == 'archives' and list(arc_folder.glob(fname + '.*')):
        #md5 hash
        h = calc_hash(f)
        #cycle to find a unique name (keep checking the hash)
        n = 0
        x = fname
        while new_file.exists() or target == 'archives' and (list(arc_folder.glob(x + '.*')) or (arc_folder / x).exists()):
            if new_file.is_file() and new_file.stat().st_size == f.stat().st_size and calc_hash(new_file) == h:
                #delete duplicate file (equal hash)
                f.unlink()
                duplicate[1] += 1
                return
            else:
                #filename pattern: "<old filename>_renamed_001_.<ext>"
                n += 1
                x = fname + '_renamed_{:0>3}_'.format(n)
                new_file = arc_folder / (x + f.suffix)
        #renamed files counter
        duplicate[0] += 1
    else:
        #moved files counters
        total[target] = total.get(target, 0) + 1
        #check/create sort folder
        if not arc_folder.exists():
            arc_folder.mkdir()
            print(f'Folder {arc_folder} has been created.')
        #check if there is a file instead of a folder
        elif arc_folder.is_file():
            n = 1
            tmp = pth / (target + str(n))
            while tmp.exists():
                n += 1
                tmp = pth / (target + str(n))
            arc_folder.replace(tmp)
            arc_folder.mkdir()
            tmp.replace(arc_folder / target)
            print(f'Folder "{arc_folder}" has been created.')
            print(f'Warning: the file "{arc_folder}" was moved into the newly created folder.')
    f.replace(new_file)
    #add to unpack list
    if target == 'archives':
        archives.append(new_file)

def process_folder(f: Path, lvl: int) -> bool:
    global FOLDERS, other, deleted
    d = bool(lvl)
    for x in f.iterdir():
        if x.is_dir():
            if x.suffix or not x.stem.lower() in FOLDERS:
                d &= process_folder(x, lvl + 1)
        else:
            for s, e in FOLDERS.items():
                if x.suffix[1:].upper() in e:
                    process_file(x, s)
                    break
            else:
                #unlisted extention = do not move the file
                other += 1
                #mark folder as "not empty"
                d = False
                #normalize file name
                s = normalize(x.stem)
                if s != x.stem:
                    x.rename(x.parent / (s + x.suffix))
    if d:
        #delete empty folder
        f.rmdir()
        deleted += 1
    else:
        #normalize folder name
        x = normalize(f.stem)
        if x != f.stem:
            f.rename(f.parent / (x + f.suffix))
    return d
            
if __name__ == '__main__':
    #check parameter
    if len(sys.argv) == 1:
        print('Please specify the path to sort files from.')
        exit(f'Usage: {sys.argv[0]} <path>')
    pth = Path(sys.argv[1])
    #check the target folder
    if not pth.exists():
        exit(f'ERROR: The specified path ({sys.argv[1]}) does not exist.')
    if not pth.is_dir():
        exit(f'ERROR: The specified path ({sys.argv[1]}) is a file (not a folder).')
    #main procedure
    process_folder(pth, 0)
    #process archives
    for x in archives:
       try:
           unpack_archive(x, pth / "archives" / x.stem)
       except ReadError:
           print(f'Warning: could not unpack the file "{x}" (ReadError).')
           archives.remove(x)
       else:
           x.unlink()
    #print counters
    for f, n in total.items():
        if n and f != 'archives':
            print('{} file{} moved to the folder "{}".'.format(*plural(n), f))
    if len(archives):
        print('{} archive{} unpacked.'.format(*plural(len(archives))))
    if duplicate[0]:
        print('{} file{} renamed due to duplicate name.'.format(*plural(duplicate[0])))
    if duplicate[1]:
        print('{} duplicate file{} deleted.'.format(*plural(duplicate[1])))
    if deleted:
        print('{} empty folder{} deleted.'.format(*plural(deleted)))
    if other:
        print('{} file{} not moved due to unsupported type (extension).'.format(*plural(other)))
    if not sum(x for x in total.values()) and not other and not sum(x for x in duplicate):
        print('0 files found to process.')

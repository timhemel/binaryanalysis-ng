# Profiling Results

The profiling was done by executing the following test script:

```
python3 perftest-cprofile.py ~/bang-testdata/openwrt-18.06.1-brcm2708-bcm2710-rpi-3-ext4-sysupgrade.img.gz
```

This executes a single threaded run of `processfile`. This is needed because the `cProfile` module does not work well with `multiprocessing`.
The profiling statistics are saved in a file `profile-<scanfile>-<run>.stats`.

In the initial run we notice that `check_for_signatures` consumes some time:

```
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
      933    0.108    0.000   14.551    0.016 /home/tim/binaryanalysis-ng/src/test/../ScanJob.py:237(check_for_signatures)
```

From the 24.373 seconds, 14.551 is spent in `check_for_signatures`. This function calls the following functions:

```
/home/tim/binaryanalysis-ng/src/test/../ScanJob.py:237(check_for_signatures)
->    1161    0.001    0.001  /home/tim/binaryanalysis-ng/src/test/../FileResult.py:28(__init__)
       266    0.000    0.000  /home/tim/binaryanalysis-ng/src/test/../FileResult.py:53(add_unpackedfile)
       933    0.000    0.000  /home/tim/binaryanalysis-ng/src/test/../ScanEnvironment.py:76(get_maxbytes)
       114    0.000    0.000  /home/tim/binaryanalysis-ng/src/test/../ScanEnvironment.py:79(get_relative_path)
       933    0.001    0.013  /home/tim/binaryanalysis-ng/src/test/../ScanEnvironment.py:83(unpack_path)
      1161    0.001    0.001  /home/tim/binaryanalysis-ng/src/test/../ScanJob.py:68(__init__)
       266    0.000    0.000  /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:55(set_last_unpacked_offset)
       266    0.000    0.000  /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:58(set_needs_unpacking)
       266    0.000    0.000  /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:61(append_unpacked_range)
      2624    0.008    0.090  /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:64(make_data_unpack_directory)
       152    0.000    0.004  /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:81(remove_data_unpack_directory)
      2358    0.010    0.128  /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:84(remove_data_unpack_directory_tree)
      1275    0.000    0.000  /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:104(get_data_unpack_directory)
       933    0.009    0.022  /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:119(open_scanfile_with_memoryview)
       933    0.001    0.004  /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:127(seek_to_last_unpacked_offset)
      1257    0.001    0.002  /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:130(get_current_offset_in_file)
      1257    0.001    0.019  /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:133(read_chunk_from_scanfile)
       933    0.000    0.003  /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:137(close_scanfile)
       324    0.000    0.001  /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:140(seek_to_find_next_signature)
    137013    1.921    2.381  /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:148(find_offsets_for_signature)
      3202    0.001    0.001  /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:172(offset_overlaps_with_unpacked_data)
      2624    0.020   11.723  /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:175(try_unpack_file_for_signatures)
      5248    0.001    0.001  /home/tim/binaryanalysis-ng/src/test/../banglogging.py:5(log)
      1161    0.000    0.001  /home/tim/binaryanalysis-ng/src/test/TestUtil.py:36(put)
      5248    0.001    0.001  /usr/lib64/python3.7/pathlib.py:684(__str__)
      1161    0.001    0.013  /usr/lib64/python3.7/pathlib.py:991(__new__)
      1161    0.000    0.000  {built-in method builtins.len}
      1257    0.002    0.002  {built-in method builtins.sorted}
      2624    0.007    0.010  {built-in method posix.chdir}
      3785    0.001    0.001  {method 'append' of 'list' objects}
      5780    0.001    0.001  {method 'get' of 'dict' objects}
    137167    0.019    0.019  {method 'update' of 'set' objects}
```

Trying to unpack for a signature takes most of the time, but finding signature offsets is called quite often and consumes a good two seconds.

# Iterator 

Hypothesis: replacing set operations with an iterator in `find_offsets_for_signature` speeds up execution.

We compared the following cases:

0001: use `find_offsets_for_signature` without an iterator:

```
candidateoffsetsfound = set()
for s in bangsignatures.signatures:
    offsets = unpacker.find_offsets_for_signature(s, self.fileresult.filesize)
    candidateoffsetsfound.update(offsets)
```

0002: use `find_offsets_for_signature` with an iterator for each signature:

```
candidateoffsetsfound = set()
for s in bangsignatures.signatures:
    offsets = { x for x in unpacker.find_offsets_for_signature_iterator(s, self.fileresult.filesize) }
    candidateoffsetsfound.update(offsets)
```

0003: use one iterator in `find_offsets_for_signature` for offsets and signatures:

```
candidateoffsetsfound = { x
    for s in bangsignatures.signatures
    for x in unpacker.find_offsets_for_signature_iterator(s,self.fileresult.filesize)
}
```

The results:

```
0001:
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
   137013    1.921    0.000    2.381    0.000 /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:148(find_offsets_for_signature)
      933    0.108    0.000   14.551    0.016 /home/tim/binaryanalysis-ng/src/test/../ScanJob.py:237(check_for_signatures)

0002:
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
   140215    1.902    0.000    2.350    0.000 /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:148(find_offsets_for_signature_iterator)
      933    0.125    0.000   14.797    0.016 /home/tim/binaryanalysis-ng/src/test/../ScanJob.py:237(check_for_signatures)

0003:
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
   140215    1.904    0.000    2.339    0.000 /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:148(find_offsets_for_signature_iterator)
      933    0.036    0.000   14.342    0.015 /home/tim/binaryanalysis-ng/src/test/../ScanJob.py:237(check_for_signatures)
```

We see a difference in the `tottime` column. Also there is a difference in the ncalls in run 0001, possibly because newer code was not merged. This may make the test less valid. However, in the cumulative time there is not much difference. Iterators make the code more readable, so we can keep it.

# Precompiling regular expressions

Hypothesis: precompiling regular expressions for signatures speeds up execution.

In run 0004, we precompile regular expressions and store them in a dictionary.

```
res = re.finditer(bangsignatures.signature_regexps[s], self.scanbytes[:self.bytesread])


def compute_signature_regexps():
    d = {}
    for ftype,signature in signatures.items():
        d[ftype] = re.compile(re.escape(signature))
    return d

signature_regexps = compute_signature_regexps()
```

The results:

```
0004:
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
   140215    1.848    0.000    2.124    0.000 /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:148(find_offsets_for_signature_iterator)
      933    0.036    0.000   13.961    0.015 /home/tim/binaryanalysis-ng/src/test/../ScanJob.py:237(check_for_signatures)
0003:
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
   140215    1.904    0.000    2.339    0.000 /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:148(find_offsets_for_signature_iterator)
      933    0.036    0.000   14.342    0.015 /home/tim/binaryanalysis-ng/src/test/../ScanJob.py:237(check_for_signatures)
```

Precompiling regular expressions does speed up execution a little bit, but we cannot say if it is significant. It costs a bit in compiling
the regexps:

```
0004:
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
   147082    0.130    0.000    0.186    0.000 /usr/lib64/python3.7/re.py:271(_compile)
```


Hypothesis: precompiling regular expressions into one expression with named patterns for signatures speeds up execution.

In run 0005 we tried compiling all signatures into one expression with named patterns. In theory, matching a more complex regular expression should not be much more expensive than a simple one. In the code we needed to make a few changes. First of all, we needed the method `find_offsets_for_all_signatures_iterator`. The regular expressions were compiled with:

```
def compute_signature_regexp():
    l = []
    for ftype,signature in signatures.items():
        s = b'(?P<%s>%s)' % (ftype.encode(),re.escape(signature))
        m = re.compile(s)
        l.append(s)
    return re.compile(b"|".join(l))

signature_regexp = compute_signature_regexp()
```

Because pattern names cannot start with a digit, we had to rename the key `7z` to `p7z` in the signature dictionary.

The results:

```
0005:
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
     4288  350.254    0.082  350.475    0.082 /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:148(find_offsets_for_all_signatures_iterator)
      933    0.045    0.000  362.757    0.389 /home/tim/binaryanalysis-ng/src/test/../ScanJob.py:237(check_for_signatures)
0003:
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
   140215    1.904    0.000    2.339    0.000 /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:148(find_offsets_for_signature_iterator)
      933    0.036    0.000   14.342    0.015 /home/tim/binaryanalysis-ng/src/test/../ScanJob.py:237(check_for_signatures)
```

One expression with named patterns is many times slower.

In 0006, we made some small optimizations in `find_offsets_for_all_signatures_iterator`. This did not help:

```
0006:
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
     4288  347.995    0.081  348.052    0.081 /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:148(find_offsets_for_all_signatures_iterator)
      933    0.044    0.000  359.956    0.386 /home/tim/binaryanalysis-ng/src/test/../ScanJob.py:237(check_for_signatures)
```

Hypothesis: fixed string matching speeds up execution.

Since all patterns are simple strings and not more complex regular expressions, perhaps Python's string functions are faster than regular expressions.

In 0007, we used a fixed string matcher, written in pure python:

```
def string_find_iter(needle, haystack, maxsize):
    pos = 0
    l = len(needle)
    while True:
        pos = haystack.find(needle,pos)
        if pos < 0 or pos + l >= maxsize:
            break
        yield pos
        # pos += 1
        pos += l
```

The last line of the routine was created to match the behaviour of `re.find_iter`: after a match, it will search for the next match at the end of the current match, i.e. overlapping matches are impossible.

The results:

```
0007:
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
   140215    0.095    0.000   10.112    0.000 /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:181(find_offsets_for_signature_find_iterator)
      933    0.036    0.000   22.300    0.024 /home/tim/binaryanalysis-ng/src/test/../ScanJob.py:237(check_for_signatures)
0003:
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
   140215    1.904    0.000    2.339    0.000 /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:148(find_offsets_for_signature_iterator)
      933    0.036    0.000   14.342    0.015 /home/tim/binaryanalysis-ng/src/test/../ScanJob.py:237(check_for_signatures)
```

String matchers are not faster than regular expressions. The reason is the call to `find` on a string:

```
   164320    0.068    0.000    9.979    0.000 /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:32(string_find_iter)
   164993    9.902    0.000    9.902    0.000 {method 'find' of 'bytearray' objects}
```

Efficient string matching algorithms for simple strings exist, but we could not find an efficient Python implementation for them.

Hypothesis: iterating over `bangsignature.signature_regexps.items()` will be quicker than looking up the regexp by signature repeatedly.

In 0008, we iterate over `regexps.items()` and not just the keys, so that we can avoid the repeated lookup to `bangsignature.signature[s]`:

```
def find_offsets_for_signature_iterator(self, s, v, filesize):
    res = re.finditer(v, self.scanbytes[:self.bytesread])
          :


candidateoffsetsfound = { x
    for s,v in bangsignatures.signature_regexps.items()
    for x in unpacker.find_offsets_for_signature_iterator(s, v, self.fileresult.filesize)
}
```

The results:

```
0008:
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
   140215    1.835    0.000    2.118    0.000 /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:206(find_offsets_for_signature_iterator)
      933    0.036    0.000   13.798    0.015 /home/tim/binaryanalysis-ng/src/test/../ScanJob.py:237(check_for_signatures)
0003:
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
   140215    1.904    0.000    2.339    0.000 /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:148(find_offsets_for_signature_iterator)
      933    0.036    0.000   14.342    0.015 /home/tim/binaryanalysis-ng/src/test/../ScanJob.py:237(check_for_signatures)
```

This saves about 1s on the tested file.


Hypothesis: lookups to `bangsignatures.signatureoffset` are expensive, storing it in a local variable saves time.

In 0011, we changed the code to avoid lookups on module, by aliasing them to local variables:

```
    def find_offsets_for_signature_iterator(self, s, v, filesize):
        signature_offset = bangsignatures.signaturesoffset.get(s,0)
        prescan_f = bangsignatures.prescan
        res = re.finditer(v, self.scanbytes[:self.bytesread])
        for r in res:
            # skip files that aren't big enough if the
            # signature is not at the start of the data
            # to be carved (example: ISO9660).
            offset = r.start()
            if offset + self.offsetinfile < signature_offset:
                 continue

            if not prescan_f(s, self.scanbytes, self.bytesread, filesize, offset, self.offsetinfile):
                continue

            yield (offset + self.offsetinfile - signature_offset, s)
```

The results:

```
0010:
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
   139234    1.860    0.000    2.145    0.000 /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:206(find_offsets_for_signature_iterator)
0011:
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
   139234    1.873    0.000    2.165    0.000 /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:206(find_offsets_for_signature_iterator)
```

The performance is similar.


# Computations over files

Another time-consuming area is computations over files, such as calculating hashes, etc. In the original run, more than 8 seconds are spent in
content computations:

```
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
     1164    0.012    0.000    8.696    0.007 /home/tim/binaryanalysis-ng/src/test/../ScanJob.py:477(do_content_computations)
```

```
/home/tim/binaryanalysis-ng/src/test/../ScanJob.py:477(do_content_computations)
->    1164    0.001    0.001  /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:28(__init__)
      3003    0.001    0.001  /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:32(subscribe)
      1164    0.003    8.659  /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:35(read)
      1164    0.000    0.000  /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:75(__init__)
      1164    0.000    0.000  /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:88(get)
       675    0.000    0.000  /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:114(__init__)
       675    0.000    0.001  /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:126(get)
      1164    0.000    0.000  /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:168(__init__)
      1164    0.000    0.000  /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:183(get)
      4167    0.001    0.001  /home/tim/binaryanalysis-ng/src/test/../FileResult.py:47(set_hashresult)
      1164    0.001    0.001  /home/tim/binaryanalysis-ng/src/test/../ScanEnvironment.py:57(get_readsize)
      1164    0.000    0.000  /home/tim/binaryanalysis-ng/src/test/../ScanEnvironment.py:60(get_createbytecounter)
      2328    0.002    0.002  /home/tim/binaryanalysis-ng/src/test/../ScanEnvironment.py:66(use_tlsh)
      1164    0.001    0.017  /home/tim/binaryanalysis-ng/src/test/../ScanEnvironment.py:83(unpack_path)
      1164    0.000    0.000  {method 'add' of 'set' objects}
      1164    0.000    0.000  {method 'items' of 'dict' objects}
```

Most of it is spent in the `read` method:

```
/home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:35(read)
->    1164    0.082    8.654  /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:55(_read_with_memory_view)
      1164    0.001    0.002  {built-in method builtins.all}
/home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:55(_read_with_memory_view)
->    1164    0.000    0.000  /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:78(initialize)
     34855    0.008    0.409  /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:81(compute)
      1164    0.000    0.000  /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:85(finalize)
       675    0.001    0.001  /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:117(initialize)
     34366    0.027    6.359  /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:120(compute)
       675    0.000    0.003  /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:123(finalize)
      1164    0.002    0.011  /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:171(initialize)
     34855    0.026    1.658  /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:175(compute)
      1164    0.002    0.007  /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:179(finalize)
      1164    0.013    0.018  {built-in method io.open}
      1164    0.003    0.003  {method 'close' of '_io.BufferedReader' objects}
     36019    0.101    0.101  {method 'readinto' of '_io.BufferedReader' objects}
      1164    0.002    0.002  {method 'seek' of '_io.BufferedReader' objects}
```

Most time consuming are the routines on line 120 (TLSH computation), 175 (hash calculation), and 81 (decide if file is text).
The latter is a method that we can change. We see that the code converts every byte in the string to a character and checks if it is in `string.printable`. Membership check is relatively expensive. The profiling information confirms this:

```
0008:
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
    34855    0.008    0.000    0.397    0.000 /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:81(compute)

/home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:81(compute)
->     446    0.000    0.000  /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:83(<genexpr>)
      1216    0.079    0.388  {built-in method builtins.all}
{built-in method builtins.all}
->    4167    0.001    0.001  /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:36(<genexpr>)
   1291562    0.221    0.309  /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:83(<genexpr>)
```

Checking whether each character is in `string.printable` takes most of the time.


Hypothesis: `decode` and `isprintable()` in `IsTextComputer` is faster:

In 0009, we decode the bytes into a string and call its method `isprintable`. As turned out later however, `isprintable` is not the same as `in string.printable`, making this test irrelevant.

Results:

```
0009:
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
    34855    0.033    0.000    0.119    0.000 /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:81(compute)
```

If we look at the call breakdown:

```
/home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:81(compute)
->   34855    0.056    0.056  {method 'decode' of 'bytes' objects}
     30038    0.004    0.004  {method 'isprintable' of 'str' objects}
```

We see that decoding the bytes to a unicode string takes the majority of the time. Unfortunately, this prints a nasty error message to the
console that cannot be disabled.

To prevent the error message and the decoding, in 0010 we use `chr(x).isprintable()`. As turned out later, `isprintable` is not the same as `in string.printable`, making this test irrelevant.

```
0010:
    34846    0.009    0.000    0.019    0.000 /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:81(compute)

/home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:81(compute)
->    1155    0.000    0.000  /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:89(<genexpr>)
      1155    0.002    0.010  {built-in method builtins.all}
```

Using `isprintable()` on `chr(x)` saves significantly. However, its results are not the same. In C++, the `isprint` function is implemented via a lookup table. Since Python does not have this, we will have to create our own.

Hypothesis: using a lookup table of printable characters saves time.

A quick experiment with timeit shows that 10000 runs on a text file of 9329 characters shows that the lookup table is about 3 times faster.
   in_printable 11.854787391988793
   my_is_printable 4.163840588007588

In 0012, we created the list `IsTextComputer.printable_chars` as a class member. To prevent an extra class member lookup, we aliased it to a local variable `pc`.

```
printable_chars = [ chr(x) in string.printable for x in range(0,256) ]

pc = self.printable_chars
self.is_text = self.is_text and all(pc[x] for x in data)
```

The result:

```
0008
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
    34855    0.008    0.000    0.397    0.000 /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:81(compute)
0012
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
    34855    0.010    0.000    0.183    0.000 /home/tim/binaryanalysis-ng/src/test/../FileContentsComputer.py:82(compute)
```

This makes the call to `compute` twice as fast.


# Overlapping signatures

The creation of `string_find_iter` pointed us at the behaviour of the code when signatures overlap. Finding offsets for the signature `aba` in `abababc` should give the offsets 0 and 2, but only gives 0. To support overlapping signatures we need to change the code.

In 0013, we use lookahead patterns for matching signatures that can overlap. In regular expressions, this is possible via lookahead patterns:

```
# the expression below allows overlapping signature matches
d[ftype] = re.compile( b'(?=' + re.escape(signature) + b')' )
```

Getting more offsets will also increase the number of unpacking operations, and likely the number of failed unpackings. These can be a problem, and should be mitigated by better and more prescans, elimination of signature scans altogether. Perhaps splitting the unpacker into a parsing phase and an unpacking phase can speed up the unpacking of falsely detected signatures.

If we look in the results at ncalls, there is virtually no difference:

```
0013:
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
   140216   77.157    0.001   77.529    0.001 /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:184(find_offsets_for_signature_iterator)
     2624    0.019    0.000   11.939    0.005 /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:228(try_unpack_file_for_signatures)

0012:
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
   140215    1.900    0.000    2.199    0.000 /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:184(find_offsets_for_signature_iterator)
     2624    0.018    0.000   11.729    0.004 /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:228(try_unpack_file_for_signatures)
```

The cumulative time however is 35 times higher! If we look at the call breakdowns of 0012 and 0013:

```
0012:
/home/tim/binaryanalysis-ng/src/test/../Unpacker.py:184(find_offsets_for_signature_iterator)
->   27307    0.010    0.037  /home/tim/binaryanalysis-ng/src/test/../bangsignatures.py:679(prescan)
    137013    0.047    0.247  /usr/lib64/python3.7/re.py:225(finditer)
    137013    0.013    0.013  {method 'get' of 'dict' objects}
     27307    0.002    0.002  {method 'start' of 're.Match' objects}

0013:
/home/tim/binaryanalysis-ng/src/test/../Unpacker.py:184(find_offsets_for_signature_iterator)
->   27437    0.011    0.042  /home/tim/binaryanalysis-ng/src/test/../bangsignatures.py:679(prescan)
    137013    0.050    0.310  /usr/lib64/python3.7/re.py:225(finditer)
    137013    0.017    0.017  {method 'get' of 'dict' objects}
     27437    0.003    0.003  {method 'start' of 're.Match' objects}
```

There is no big difference in the number of calls or the time spent in the functions, so it must be the lookahead patterns that are expensive.
Like named patterns, it adds quite some overhead. We suspect that adding groups into a regular expression immediately makes matching them more expensive.

Inspired by `string_find_iter`, we created our own iterator, but instead of using the `find` method on strings, we use `search` on a regular expression object. This code is in 0014:

```
candidateoffsetsfound = { x
    for s,v in bangsignatures.signature_regexps.items()
    for x in unpacker.find_offsets_for_overlapping_signature_iterator(s, v, self.fileresult.filesize)
}

def re_find_overlapping_iter(pattern, buf, maxsize):
    pos = 0
    while True:
        m = pattern.search(buf[pos:maxsize])
        if m:
            pos += m.start()
            yield pos
            pos += 1
        else:
            break

def find_offsets_for_overlapping_signature_iterator(self, s, v, filesize):
    signature_offset = bangsignatures.signaturesoffset.get(s,0)
    prescan_f = bangsignatures.prescan
    res = re_find_overlapping_iter(v, self.scanbytes, self.bytesread)
    for offset in res:
        # skip files that aren't big enough if the
        # signature is not at the start of the data
        # to be carved (example: ISO9660).
        if offset + self.offsetinfile < signature_offset:
            continue

        if not prescan_f(s, self.scanbytes, self.bytesread, filesize, offset, self.offsetinfile):
            continue

        yield (offset + self.offsetinfile - signature_offset, s)

def find_offsets_for_signature_iterator(self, s, v, filesize):
    signature_offset = bangsignatures.signaturesoffset.get(s,0)
    prescan_f = bangsignatures.prescan
    res = re_find_overlapping_iter(v, self.scanbytes, self.bytesread)
```

The results:

```
0014:
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
   140216    0.086    0.000    1.980    0.000 /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:195(find_offsets_for_overlapping_signature_iterator)
   164450    0.056    0.000    1.845    0.000 /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:43(re_find_overlapping_iter)
     2624    0.020    0.000   12.098    0.005 /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:257(try_unpack_file_for_signatures)

0012:
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
   140215    1.900    0.000    2.199    0.000 /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:184(find_offsets_for_signature_iterator)
     2624    0.018    0.000   11.729    0.004 /home/tim/binaryanalysis-ng/src/test/../Unpacker.py:228(try_unpack_file_for_signatures)
```

The overlapping iterator is not more expensive, and might lead to more results.
We can see how many more signature candidates were found by looking at the number of calls to prescan:

```
0014:
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
    27437    0.010    0.000    0.037    0.000 /home/tim/binaryanalysis-ng/src/test/../bangsignatures.py:679(prescan)
0012:
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
    27307    0.010    0.000    0.037    0.000 /home/tim/binaryanalysis-ng/src/test/../bangsignatures.py:679(prescan)
```

There is a difference of 130 calls, which means that 130 extra signature candidates were detected.


# Trying to unpack a file

For a run on the openwrt test file, with commit 456874809437342480e0353a3f14921b901bbd98 we gathered the following results from the logs:

| phase   | calls |
|---------|-------|
| TRYING  | 6123  |
| FAIL    | 5831  |
| SUCCESS | 310   |

FAIL and SUCCESS together are more than TRYING, because extension based unpacks also log FAIL or SUCCESS events.
Still, the number of failed unpackings is large.

In commit 05b487b71e6385a864383b9ca4d51d0ef11f4d20, profiling code was added to the unpackers to log the time (real time in ns) needed for each call to the unpacker. The results show the following

```
unpacker             #pass #fail    time-pass    time-fail      %pass      %fail
--------------------------------------------------------------------------------
unpackExt2               1    22  10310310095      2818750      99.97       0.03
unpackGzip               2     0   1111139923            0     100.00       0.00
unpackFAT                0    53            0    118241970       0.00     100.00
unpackIHex               0   702            0     83890102       0.00     100.00
unpackSREC               0   702            0     80981028       0.00     100.00
unpackKernelConfig       1   701      1306310     39556386       3.20      96.80
unpackBase64             9   692      1571611     36132697       4.17      95.83
unpackJPEG               0   951            0     33581712       0.00     100.00
unpackScript            17   675       902061     32112441       2.73      97.27
unpackELF              112    46     26659227      3055226      89.72      10.28
unpackICO                1   183     20781810      7660523      73.07      26.93
unpackCSS                2     0     28019509            0     100.00       0.00
unpackPNM                0   560            0     19022204       0.00     100.00
unpackDeviceTree       106     0     17410010            0     100.00       0.00
unpackXML                5     0     11318811            0     100.00       0.00
unpackLZMA               0    51            0     11156410       0.00     100.00
unpackCompress           0    15            0     10132124       0.00     100.00
unpackTar                0     3            0      8462828       0.00     100.00
unpackJFFS2              0   128            0      5643613       0.00     100.00
unpackPNG               22     0      5230492            0     100.00       0.00
unpackGIF               20     0      3905343            0     100.00       0.00
unpackTerminfo           0    94            0      3843477       0.00     100.00
unpackMinix1L            0    71            0      2758429       0.00     100.00
unpackAIFF               0    70            0      2491883       0.00     100.00
unpack_pak               0    52            0      1821411       0.00     100.00
unpackDex                0    28            0      1101480       0.00     100.00
unpackTRX                2     0       721674            0     100.00       0.00
unpackXZ                 0     2            0       643950       0.00     100.00
unpackANI                0    11            0       639990       0.00     100.00
unpackJSON               6     0       476531            0     100.00       0.00
unpackBMP                0    10            0       361583       0.00     100.00
unpackCpio               0     5            0       287560       0.00     100.00
unpackShadow             1     1        85350        54658      60.96      39.04
unpackSGI                0     3            0       105041       0.00     100.00
unpackGroup              1     0        68958            0     100.00       0.00
unpackPasswd             1     0        67449            0     100.00       0.00
unpackFstab              1     0        54307            0     100.00       0.00
--------------------------------------------------------------------------------
total                  310  5831  11540029471    506557476      95.80       4.20
```

The unpacker that consumes most, `unpackExt2`, only spent 0.03% of its time on failed unpackings. `unpackFAT` on the other hand, spent all of the 118241970 ns (118 ms) on failed unpacks.

To improve performance, we can:
* make successful unpackings more efficient
* make failed unpackings more efficient
* reduce the number of failed unpackings

## Base64

Hypothesis: need for Base64 unpacks can be reduced.

If we split the base64 failures, we see:

|----:|------------------------------------------|
| 537 | invalid character not in base16/32/64 alphabets |
| 87 | inconsistent line wrapping |
| 64 | not a valid base64 file |
| 4 | file too small |

The check for invalid characters checks if the file contains a space in the middle.

We introduced two functions, `check_base64_chars`, `check_base64_spaces` and `check_base64_consistent_lines`. For each check, the file is opened and read.

On the test file, less files were identified as base64:

```
openwrt-18.06.1-brcm2708-bcm2710-rpi-3-ext4-sysupgrade.img.gz-gzip-1/openwrt-18.06.1-brcm2708-bcm2710-rpi-3-ext4-sysupgrade.img-ext2-1/etc/openwrt_version-base64-1/unpacked.base64
openwrt-18.06.1-brcm2708-bcm2710-rpi-3-ext4-sysupgrade.img.gz-gzip-1/openwrt-18.06.1-brcm2708-bcm2710-rpi-3-ext4-sysupgrade.img-ext2-1/etc/modules.d/25-nls-utf8-base64-1/unpacked.base64
openwrt-18.06.1-brcm2708-bcm2710-rpi-3-ext4-sysupgrade.img.gz-gzip-1/openwrt-18.06.1-brcm2708-bcm2710-rpi-3-ext4-sysupgrade.img-ext2-1/etc/modules.d/42-ip6tables-base64-1/unpacked.base64

```

These are all false positives. The unpack statistics show the following:

```
before: unpackBase64             9   692      1571611     36132697       4.17      95.83
after:  unpackBase64             6   695      1454942     29646770       4.68      95.32

```

The new base64 code costs  (1454942 + 29646770) / ( 1571611  +  36132697) = 0.8248848380933023 of the execution time of the old code.

In profile run 0016, we profiled the whole unpacking routine:

```
/home/tim/binaryanalysis-ng/src/test/../bangunpack.py:10495(unpackBase64)
->     707    0.000    0.012  /home/tim/binaryanalysis-ng/src/test/../ScanEnvironment.py:83(unpack_path)
       697    0.007    0.009  /home/tim/binaryanalysis-ng/src/test/../bangunpack.py:10464(check_base64_chars)
        18    0.000    0.000  /home/tim/binaryanalysis-ng/src/test/../bangunpack.py:10471(check_base64_spaces)
        18    0.000    0.000  /home/tim/binaryanalysis-ng/src/test/../bangunpack.py:10479(check_base64_consistent_lines)
        15    0.000    0.000  /usr/lib64/python3.7/base64.py:97(standard_b64decode)
        45    0.000    0.000  /usr/lib64/python3.7/base64.py:180(b32decode)
        15    0.000    0.000  /usr/lib64/python3.7/base64.py:253(b16decode)
         6    0.000    0.000  /usr/lib64/python3.7/posixpath.py:75(join)
       233    0.000    0.000  {built-in method builtins.chr}
        12    0.000    0.000  {built-in method builtins.len}
       754    0.009    0.012  {built-in method io.open}
        12    0.000    0.000  {method 'append' of 'list' objects}
       712    0.002    0.002  {method 'close' of '_io.BufferedReader' objects}
         6    0.000    0.000  {method 'close' of '_io.BufferedWriter' objects}
        36    0.000    0.000  {method 'close' of '_io.TextIOWrapper' objects}
        15    0.000    0.000  {method 'readinto' of '_io.BufferedReader' objects}
        30    0.000    0.000  {method 'replace' of 'bytearray' objects}
         6    0.000    0.000  {method 'write' of '_io.BufferedWriter' objects}
```

697 - 18 = 679 files are rejected in the first check `check_base64_chars`.



# Overview of runs

Note: sometimes, more experiments were done without committing the code in between. Therefore, the commit does not always
represent the actual code that has been profiled.

| run	 | branch	 | commit                                   |
|--------|---------------|------------------------------------------|
| 0001	 | performance	 | 4a5b610aa63798a373dff3fa4de08f189d3ebe9f |
| 0002	 | performance	 | 4a5b610aa63798a373dff3fa4de08f189d3ebe9f |
| 0003	 | performance	 | 4a5b610aa63798a373dff3fa4de08f189d3ebe9f |
| 0004	 | performance	 | effe55867078ed96505883279e49af5a0c8d832c |
| 0005	 | performance	 | 787b19b222cc024fd10d12335414eea60d750d7b |
| 0006	 | performance	 | 7ad6f61c02349bc5e2f84c2d641dc938ee0fd9e6 |
| 0007	 | performance	 | 592937d078ef2e326d6b544f01ec4c971ef1214d |
| 0008	 | performance	 | 592937d078ef2e326d6b544f01ec4c971ef1214d |
| 0009	 | performance	 | 1d679c7bee0aa184e0845059733fa4160b7bc907 |
| 0010	 | performance	 | ee38e0ab6f13caaff3c99f7e3bcfb2549013c2f5 |
| 0011	 | performance	 | e1f28d6682d7a802b3db2b5ded6b0e29726b4d89 |
| 0012	 | performance	 | ca7b404764b1f2a132f96562782cf203ecfc7914 |
| 0013	 | performance	 | ad00d846d5b8f708c92e5e03f9e3c6a2636418b3 |
| 0014	 | performance	 | c4e2e99d0acb9adc070940e209cca03da8e76725 |
| 0015	 | performance	 | d95f0b8cb4453ef2f242a344a1205a5bd9192fd1 |
| 0016	 | performance	 | d95f0b8cb4453ef2f242a344a1205a5bd9192fd1 |




Headless Ghidra helper scripts used during the analysis (Ghidra 12.1 with the
AEON R2 module, program `mapp_full.bin` loaded at 0x200000).

```
analyzeHeadless <project_dir> <project> -process mapp_full.bin -noanalysis \
    -scriptPath ghidra_scripts -postScript Decomp.java out.c 0x2573aa 0x261097
```

| Script | Arguments | Output |
|---|---|---|
| `Decomp.java` | output file, then function addresses | decompiled C with caller lists |
| `DecompAll.java` | output file | every function decompiled |
| `Xref.java` | addresses | references to each address, with the containing function |
| `Lst.java` | from, to | instructions with their bytes |
| `CallArgs.java` | function addresses | every call site and the instruction that loads the first argument |
| `FnAt.java` | addresses | whether a function starts at / contains each address |
| `AllStrRefs.java` | none | `build/string_refs.txt`: strings and the code that references them |

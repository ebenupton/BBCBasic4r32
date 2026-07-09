# Builds the two variants of the 65C02-optimised BBC BASIC 4r32 ROM
# from the single conditional source disassembly/Basic432.asm:
#
#   Basic432_fast.bin    - speed features (see FAST.md)
#   Basic432_basicv.bin  - WHILE/ENDWHILE + block IF/ELSE/ENDIF (see BASICV.md)
#
# The variants are mutually exclusive: the 16K image cannot hold both.
# Requires beebasm >= 1.10 (for -D); override with BEEBASM=/path/to/beebasm.

BEEBASM ?= beebasm
DIS     := disassembly

ROMS := $(DIS)/Basic432_basicv.bin $(DIS)/Basic432_fast.bin

all: $(ROMS)

$(DIS)/Basic432_basicv.bin: $(DIS)/Basic432.asm
	cd $(DIS) && $(BEEBASM) -i Basic432.asm -D BASICV=1

$(DIS)/Basic432_fast.bin: $(DIS)/Basic432.asm
	cd $(DIS) && $(BEEBASM) -i Basic432.asm -D BASICV=0

# Verify the built ROMs match the committed reference images.
check: all
	cmp $(DIS)/Basic432_basicv.bin $(DIS)/Basic432_basicv.orig
	cmp $(DIS)/Basic432_fast.bin $(DIS)/Basic432_fast.orig
	@echo "both variants match their reference images"

# Update the committed reference images and hex dumps (run after an
# intentional ROM change, then commit the results).
refs: all
	cp $(DIS)/Basic432_basicv.bin $(DIS)/Basic432_basicv.orig
	cp $(DIS)/Basic432_fast.bin   $(DIS)/Basic432_fast.orig
	xxd $(DIS)/Basic432_basicv.bin > $(DIS)/Basic432_basicv.hex
	xxd $(DIS)/Basic432_fast.bin   > $(DIS)/Basic432_fast.hex

# Refresh the committed pre-built ROM images in roms/.
roms: all
	cp $(DIS)/Basic432_fast.bin   roms/Basic432_fast.rom
	cp $(DIS)/Basic432_basicv.bin roms/Basic432_basicv.rom

# Rebuild the test disc: both ROMs plus the *EXEC-able test suites.
disc: all
	python3 tools/mkssd.py tests/basic432.ssd \
	    BASICV=$(DIS)/Basic432_basicv.bin,8000,8000 \
	    FAST=$(DIS)/Basic432_fast.bin,8000,8000 \
	    STEST=tests/selftest.txt \
	    WTEST=tests/whiletest.txt \
	    ITEST=tests/iftest.txt \
	    BSEARCH=tests/bsearch.tok,0E00,802B

clean:
	rm -f $(ROMS)

.PHONY: all check refs roms disc clean

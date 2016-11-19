SRCFILES = $(wildcard *.ome)
OUTFILES = $(SRCFILES:%.ome=%)
OMEFLAGS = --backend=clang --use-musl --static

all : $(OUTFILES)

clean :
	rm -f $(OUTFILES)

% : %.ome
	ome $(OMEFLAGS) -o $@ $<

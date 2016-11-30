SRCFILES = $(wildcard *.ome)
OUTFILES = $(SRCFILES:%.ome=%)
OMEFLAGS =

all : $(OUTFILES)

clean :
	rm -f $(OUTFILES)

% : %.ome
	ome $(OMEFLAGS) -o $@ $<

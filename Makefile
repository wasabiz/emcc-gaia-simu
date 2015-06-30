SRC    = sim.c debug.c
TARGET = sim.js

CC = emcc
CFLAGS = -Wall -Wextra -O2 -std=gnu99 -g --embed-file xv6.img -s EMTERPRETIFY=1 -s EMTERPRETIFY_ASYNC=1
LDLIBS = -lm

all: sim.js
	cp sim.js sim.js.mem site/

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) $(SRC) $(LDLIBS) -o $(TARGET)

PHONY: clean
clean:
	rm -f $(TARGET) $(TARGET).mem *.out *.out.s


all: fan

fan: fan.c
	$(CC) -o $@ $^ $(CFLAGS) -lsensors

clean:
	rm -f fan

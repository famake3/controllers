#include <sensors/sensors.h>
#include <stdio.h>


void printemps()
{
    sensors_chip_name const * cn;
    int c = 0;
    while ((cn = sensors_get_detected_chips(0, &c)) != 0) {
        printf("chip name prefix: %s, path %s\n", cn->prefix, cn->path);

        sensors_feature const *feat;
        int f = 0;

        while ((feat = sensors_get_features(cn, &f)) != 0) {
            printf("feature %d: %s\n", f, feat->name);

            sensors_subfeature const *subf;
            int s = 0;

            while ((subf = sensors_get_all_subfeatures(cn, feat, &s)) != 0) {
                printf("feature %d subfeature %d: %s (#%d): ", f, s, subf->name,  subf->number);
                double val;
                if (subf->flags & SENSORS_MODE_R) {
                    int rc = sensors_get_value(cn, subf->number, &val);
                    if (rc < 0) {
                        printf("ERROR: %d\n", rc);
                    } else {
                        printf("%f\n", val);
                    }
                }
            }
        }
    }
}

int main(int argc, char** argv) {
    if (argc != 3) {
        printf("Usage: fan config_file serIal_port\n");
        printf("DEBUG: continuing anyway\n");
        //return 1;
    }
    //const char* serial_port = argv[1];
    //const char* config_file = argv[2];

    if (sensors_init(NULL) != 0) {
        printf("FATAL: sensors library failed to init.");
        return 1;
    }

    

    printemps();
    return 0;
}

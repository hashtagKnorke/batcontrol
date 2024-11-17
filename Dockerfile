FROM alpine:3.20

# add required libraries as py3-* Alpine packages 
# (this is equivalent to doing 
# pip install -r requirements.txt )
# the dependencies here need to reflect what batcontrol depends on
RUN apk add --no-cache \
            python3 \
            py3-numpy \
            py3-pandas\
            py3-yaml\
            py3-requests\
            py3-paho-mqtt


# set the python path to include the thermia API submodule package
ENV PYTHONPATH="/batcontrol/thermia_online_api:${PYTHONPATH}"

## alternative to using the pythonpath is to copy the submodule package into the working directory

COPY ./ /batcontrol
WORKDIR /batcontrol
RUN ln -s /data/ /batcontrol/config/

CMD [ "./batcontrol.py" ]
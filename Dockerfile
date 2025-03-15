FROM python AS complier

WORKDIR /app
COPY nexus_npm_sync.py ./nexus_npm_sync.py
COPY requirements.txt ./requirements.txt
COPY libs ./libs

RUN apt-get update \
    && apt-get install -y build-essential patchelf \
    && pip install staticx pyinstaller

RUN pip install -r requirements.txt

RUN pyinstaller --onefile --clean --strip --log-level=DEBUG --hidden-import=libs.config --hidden-import=libs.log nexus_npm_sync.py
RUN staticx /app/dist/nexus_npm_sync /nexus_npm_sync

FROM scratch
WORKDIR /
COPY --from=complier /nexus_npm_sync /
COPY --from=complier /tmp /tmp
COPY config.yaml /config.yaml
ENTRYPOINT ["/nexus_npm_sync"]

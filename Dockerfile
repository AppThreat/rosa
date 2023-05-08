FROM almalinux/9-minimal:latest as builder

ENV GOSEC_VERSION=2.15.0 \
    TFSEC_VERSION=1.28.1 \
    KUBESEC_VERSION=2.11.4 \
    KUBE_SCORE_VERSION=2.13.0 \
    DETEKT_VERSION=1.22.0 \
    GITLEAKS_VERSION=8.16.3 \
    GRADLE_VERSION=8.1.1 \
    GRADLE_HOME=/opt/gradle-${GRADLE_VERSION} \
    SC_VERSION=2023.1.3 \
    PMD_VERSION=6.55.0 \
    PMD_CMD="/opt/pmd-bin-${PMD_VERSION}/bin/run.sh pmd" \
    FSB_VERSION=1.12.0 \
    SB_CONTRIB_VERSION=7.6.0 \
    SB_VERSION=4.7.3 \
    GOPATH=/opt/app-root/go \
    GO_VERSION=1.20.4 \
    ORAS_VERSION="1.0.0" \
    PATH=${PATH}:${GRADLE_HOME}/bin:${GOPATH}/bin:/usr/local/bin/appthreat:

USER root

RUN microdnf install -y make \
        findutils tar shadow-utils unzip zip sudo xz wget which unzip \
        nodejs npm java-17-openjdk-headless libsecret \
    && curl -LO "https://dl.google.com/go/go${GO_VERSION}.linux-amd64.tar.gz" \
    && tar -C /usr/local -xzf go${GO_VERSION}.linux-amd64.tar.gz \
    && rm go${GO_VERSION}.linux-amd64.tar.gz \
    && npm install --unsafe-perm -g yarn \
    && microdnf clean all

RUN mkdir -p /usr/local/bin/appthreat \
    && curl -LO "https://github.com/securego/gosec/releases/download/v${GOSEC_VERSION}/gosec_${GOSEC_VERSION}_linux_amd64.tar.gz" \
    && tar -C /usr/local/bin/appthreat/ -xvf gosec_${GOSEC_VERSION}_linux_amd64.tar.gz \
    && chmod +x /usr/local/bin/appthreat/gosec \
    && rm gosec_${GOSEC_VERSION}_linux_amd64.tar.gz \
    && curl -LO "https://github.com/oras-project/oras/releases/download/v${ORAS_VERSION}/oras_${ORAS_VERSION}_linux_amd64.tar.gz" \
    && mkdir -p oras-install/ \
    && tar -zxf oras_${ORAS_VERSION}_*.tar.gz -C oras-install/ \
    && sudo mv oras-install/oras /usr/local/bin/appthreat/ \
    && chmod +x /usr/local/bin/appthreat/oras \
    && rm -rf oras_${ORAS_VERSION}_*.tar.gz oras-install/ \
    && oras pull ghcr.io/appthreat/cpggen-bin:v1 -o /usr/local/bin/appthreat/ \
    && rm /usr/local/bin/appthreat/cpggen \
    && mv /usr/local/bin/appthreat/cpggen-linux-amd64 /usr/local/bin/appthreat/cpg \
    && chmod +x /usr/local/bin/appthreat/cpg
RUN curl -LO "https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip" \
    && unzip -q gradle-${GRADLE_VERSION}-bin.zip -d /opt/ \
    && chmod +x /opt/gradle-${GRADLE_VERSION}/bin/gradle \
    && rm gradle-${GRADLE_VERSION}-bin.zip \
    && curl -LO "https://github.com/dominikh/go-tools/releases/download/${SC_VERSION}/staticcheck_linux_amd64.tar.gz" \
    && tar -C /tmp -xvf staticcheck_linux_amd64.tar.gz \
    && chmod +x /tmp/staticcheck/staticcheck \
    && cp /tmp/staticcheck/staticcheck /usr/local/bin/appthreat/staticcheck \
    && rm staticcheck_linux_amd64.tar.gz
RUN curl -L "https://github.com/zricethezav/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks-linux-amd64" -o "/usr/local/bin/appthreat/gitleaks" \
    && chmod +x /usr/local/bin/appthreat/gitleaks \
    && curl -L "https://github.com/aquasecurity/tfsec/releases/download/v${TFSEC_VERSION}/tfsec-linux-amd64" -o "/usr/local/bin/appthreat/tfsec" \
    && chmod +x /usr/local/bin/appthreat/tfsec
RUN curl -L "https://github.com/zegl/kube-score/releases/download/v${KUBE_SCORE_VERSION}/kube-score_${KUBE_SCORE_VERSION}_linux_amd64" -o "/usr/local/bin/appthreat/kube-score" \
    && chmod +x /usr/local/bin/appthreat/kube-score \
    && wget "https://github.com/pmd/pmd/releases/download/pmd_releases%2F${PMD_VERSION}/pmd-bin-${PMD_VERSION}.zip" \
    && unzip -q pmd-bin-${PMD_VERSION}.zip -d /opt/ \
    && rm pmd-bin-${PMD_VERSION}.zip
RUN curl -L "https://github.com/detekt/detekt/releases/download/v${DETEKT_VERSION}/detekt-cli-${DETEKT_VERSION}-all.jar" -o "/usr/local/bin/appthreat/detekt-cli.jar" \
    && curl -LO "https://github.com/controlplaneio/kubesec/releases/download/v${KUBESEC_VERSION}/kubesec_linux_amd64.tar.gz" \
    && tar -C /usr/local/bin/appthreat/ -xvf kubesec_linux_amd64.tar.gz \
    && rm kubesec_linux_amd64.tar.gz \
    && curl -LO "https://github.com/spotbugs/spotbugs/releases/download/${SB_VERSION}/spotbugs-${SB_VERSION}.tgz" \
    && tar -C /opt/ -xvf spotbugs-${SB_VERSION}.tgz \
    && rm spotbugs-${SB_VERSION}.tgz \
    && curl -LO "https://repo1.maven.org/maven2/com/h3xstream/findsecbugs/findsecbugs-plugin/${FSB_VERSION}/findsecbugs-plugin-${FSB_VERSION}.jar" \
    && mv findsecbugs-plugin-${FSB_VERSION}.jar /opt/spotbugs-${SB_VERSION}/plugin/findsecbugs-plugin.jar \
    && curl -LO "https://repo1.maven.org/maven2/com/mebigfatguy/sb-contrib/sb-contrib/${SB_CONTRIB_VERSION}/sb-contrib-${SB_CONTRIB_VERSION}.jar" \
    && mv sb-contrib-${SB_CONTRIB_VERSION}.jar /opt/spotbugs-${SB_VERSION}/plugin/sb-contrib.jar

FROM almalinux/9-minimal:latest

LABEL maintainer="appthreat" \
      org.opencontainers.image.authors="Team AppThreat <cloud@appthreat.com>" \
      org.opencontainers.image.source="https://github.com/appthreat/rosa" \
      org.opencontainers.image.url="https://github.com/appthreat/rosa" \
      org.opencontainers.image.version="3.0.0" \
      org.opencontainers.image.vendor="AppThreat" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.title="rosa" \
      org.opencontainers.image.description="Risk Oriented Security Analysis tool from AppThreat" \
      org.opencontainers.docker.cmd="docker run --rm -v $(pwd):/app:rw -t ghcr.io/appthreat/rosa rosa --build"

ENV APP_SRC_DIR=/usr/local/src \
    DEPSCAN_CMD="/usr/bin/depscan" \
    PMD_CMD="/opt/pmd-bin/bin/run.sh pmd" \
    PMD_JAVA_OPTS="" \
    SB_VERSION=4.7.3 \
    PMD_VERSION=6.55.0 \
    SPOTBUGS_HOME=/opt/spotbugs \
    JAVA_HOME="/etc/alternatives/jre_17" \
    JAVA_17_HOME="/etc/alternatives/jre_17" \
    GRADLE_VERSION=8.1.1 \
    GRADLE_HOME=/opt/gradle \
    GRADLE_CMD=gradle \
    PYTHONUNBUFFERED=1 \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    GO_VERSION=1.20.4 \
    GO111MODULE=auto \
    GOARCH=amd64 \
    GOOS=linux \
    CGO_ENABLED=0 \
    NVD_EXCLUDE_TYPES="o,h" \
    PATH=/usr/local/src/:${PATH}:/opt/gradle/bin:/usr/local/go/bin:/opt/phpsast/vendor/bin:

COPY --from=builder /usr/local/bin/appthreat /usr/local/bin
COPY --from=builder /opt/pmd-bin-${PMD_VERSION} /opt/pmd-bin
COPY --from=builder /opt/spotbugs-${SB_VERSION} /opt/spotbugs
COPY --from=builder /opt/gradle-${GRADLE_VERSION} /opt/gradle
COPY . /usr/local/src/

USER root

RUN echo -e "[nodejs]\nname=nodejs\nstream=20\nprofiles=\nstate=enabled\n" > /etc/dnf/modules.d/nodejs.module \
    && microdnf install -y php php-curl php-zip php-bcmath php-json php-pear php-mbstring php-devel make gcc \
      findutils tar shadow-utils unzip zip sudo xz wget which maven \
      nodejs jq git-core java-17-openjdk-headless python3 python3-devel \
    && curl -LO "https://dl.google.com/go/go${GO_VERSION}.linux-amd64.tar.gz" \
    && tar -C /usr/local -xzf go${GO_VERSION}.linux-amd64.tar.gz \
    && rm go${GO_VERSION}.linux-amd64.tar.gz \
    && npm install --unsafe-perm -g yarn \
    && php -r "copy('https://getcomposer.org/installer', 'composer-setup.php');" && php composer-setup.php \
    && mv composer.phar /usr/local/bin/composer \
    && pip3 install --no-cache-dir poetry==1.3.2 \
    && poetry config virtualenvs.create false \
    && cd /usr/local/src/ && poetry install --no-cache --without dev \
    && npm install --no-audit --progress=false --omit=dev -g @cyclonedx/cdxgen @microsoft/rush --unsafe-perm \
    && mkdir -p /opt/phpsast && cd /opt/phpsast && composer require --quiet --no-cache --dev vimeo/psalm \
    && rm -rf /var/cache/yum \
    && microdnf remove -y python3-devel php-fpm php-devel php-pear automake make gcc gcc-c++ libtool \
    && microdnf clean all

WORKDIR /app

CMD [ "rosa" ]

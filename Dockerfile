FROM almalinux/9-minimal:latest as builder

ARG CLI_VERSION
ARG BUILD_DATE

ENV GOSEC_VERSION=2.14.0 \
    TFSEC_VERSION=0.63.1 \
    KUBESEC_VERSION=2.11.4 \
    KUBE_SCORE_VERSION=1.13.0 \
    SHELLCHECK_VERSION=0.7.2 \
    DETEKT_VERSION=1.22.0 \
    GITLEAKS_VERSION=7.6.1 \
    GRADLE_VERSION=7.2 \
    GRADLE_HOME=/opt/gradle-${GRADLE_VERSION} \
    SC_VERSION=0.3.3 \
    PMD_VERSION=6.53.0 \
    PMD_CMD="/opt/pmd-bin-${PMD_VERSION}/bin/run.sh pmd" \
    JQ_VERSION=1.6 \
    FSB_VERSION=1.12.0 \
    SB_CONTRIB_VERSION=7.4.7 \
    SB_VERSION=4.7.3 \
    GOPATH=/opt/app-root/go \
    GO_VERSION=1.20 \
    PATH=${PATH}:${GRADLE_HOME}/bin:${GOPATH}/bin:

USER root

RUN microdnf install -y make \
        findutils tar shadow-utils unzip zip sudo xz wget which unzip \
        nodejs npm java-11-openjdk-headless libsecret \
    && curl -LO "https://dl.google.com/go/go${GO_VERSION}.linux-amd64.tar.gz" \
    && tar -C /usr/local -xzf go${GO_VERSION}.linux-amd64.tar.gz \
    && rm go${GO_VERSION}.linux-amd64.tar.gz \
    && npm install --unsafe-perm -g yarn \
    && microdnf clean all

RUN mkdir -p /usr/local/bin/appthreat \
    && curl -LO "https://github.com/securego/gosec/releases/download/v${GOSEC_VERSION}/gosec_${GOSEC_VERSION}_linux_amd64.tar.gz" \
    && tar -C /usr/local/bin/appthreat/ -xvf gosec_${GOSEC_VERSION}_linux_amd64.tar.gz \
    && chmod +x /usr/local/bin/appthreat/gosec \
    && rm gosec_${GOSEC_VERSION}_linux_amd64.tar.gz
RUN curl -LO "https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip" \
    && unzip -q gradle-${GRADLE_VERSION}-bin.zip -d /opt/ \
    && chmod +x /opt/gradle-${GRADLE_VERSION}/bin/gradle \
    && rm gradle-${GRADLE_VERSION}-bin.zip \
    && curl -LO "https://github.com/koalaman/shellcheck/releases/download/v${SHELLCHECK_VERSION}/shellcheck-v${SHELLCHECK_VERSION}.linux.x86_64.tar.xz" \
    && tar -C /tmp/ -xvf shellcheck-v${SHELLCHECK_VERSION}.linux.x86_64.tar.xz \
    && cp /tmp/shellcheck-v${SHELLCHECK_VERSION}/shellcheck /usr/local/bin/appthreat/shellcheck \
    && chmod +x /usr/local/bin/appthreat/shellcheck \
    && curl -LO "https://github.com/dominikh/go-tools/releases/download/v${SC_VERSION}/staticcheck_linux_amd64.tar.gz" \
    && tar -C /tmp -xvf staticcheck_linux_amd64.tar.gz \
    && chmod +x /tmp/staticcheck/staticcheck \
    && cp /tmp/staticcheck/staticcheck /usr/local/bin/appthreat/staticcheck \
    && rm staticcheck_linux_amd64.tar.gz
RUN curl -L "https://github.com/zricethezav/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks-linux-amd64" -o "/usr/local/bin/appthreat/gitleaks" \
    && chmod +x /usr/local/bin/appthreat/gitleaks \
    && curl -L "https://github.com/aquasecurity/tfsec/releases/download/v${TFSEC_VERSION}/tfsec-linux-amd64" -o "/usr/local/bin/appthreat/tfsec" \
    && chmod +x /usr/local/bin/appthreat/tfsec \
    && rm shellcheck-v${SHELLCHECK_VERSION}.linux.x86_64.tar.xz
RUN curl -L "https://github.com/zegl/kube-score/releases/download/v${KUBE_SCORE_VERSION}/kube-score_${KUBE_SCORE_VERSION}_linux_amd64" -o "/usr/local/bin/appthreat/kube-score" \
    && chmod +x /usr/local/bin/appthreat/kube-score \
    && wget "https://github.com/pmd/pmd/releases/download/pmd_releases%2F${PMD_VERSION}/pmd-bin-${PMD_VERSION}.zip" \
    && unzip -q pmd-bin-${PMD_VERSION}.zip -d /opt/ \
    && rm pmd-bin-${PMD_VERSION}.zip \
    && curl -L "https://github.com/stedolan/jq/releases/download/jq-${JQ_VERSION}/jq-linux64" -o "/usr/local/bin/appthreat/jq" \
    && chmod +x /usr/local/bin/appthreat/jq
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
    && mv sb-contrib-${SB_CONTRIB_VERSION}.jar /opt/spotbugs-${SB_VERSION}/plugin/sb-contrib.jar \
    && curl "https://cdn.shiftleft.io/download/sl" > /usr/local/bin/appthreat/sl \
    && chmod a+rx /usr/local/bin/appthreat/sl

FROM almalinux/9-minimal:latest

LABEL maintainer="appthreat" \
      org.opencontainers.image.authors="Team AppThreat <cloud@appthreat.com>" \
      org.opencontainers.image.source="https://github.com/appthreat/rosa" \
      org.opencontainers.image.url="https://github.com/appthreat/rosa" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.vendor="AppThreat" \
      org.opencontainers.image.licenses="GPL-3.0-or-later" \
      org.opencontainers.image.title="rosa" \
      org.opencontainers.image.description="Risk Oriented Security Analysis tool from AppThreat" \
      org.opencontainers.docker.cmd="docker run --rm -v $(pwd):/app:rw -t ghcr.io/appthreat/rosa rosa --build"

ENV APP_SRC_DIR=/usr/local/src \
    DEPSCAN_CMD="/usr/local/bin/depscan" \
    PMD_CMD="/opt/pmd-bin/bin/run.sh pmd" \
    PMD_JAVA_OPTS="--enable-preview" \
    SB_VERSION=4.7.3 \
    PMD_VERSION=6.53.0 \
    SPOTBUGS_HOME=/opt/spotbugs \
    JAVA_HOME=/usr/lib/jvm/jre-11-openjdk \
    SCAN_JAVA_HOME=/usr/lib/jvm/jre-11-openjdk \
    SCAN_JAVA_11_HOME=/usr/lib/jvm/jre-11-openjdk \
    SCAN_JAVA_8_HOME=/usr/lib/jvm/jre-1.8.0 \
    GRADLE_VERSION=7.2 \
    GRADLE_HOME=/opt/gradle \
    GRADLE_CMD=gradle \
    PYTHONUNBUFFERED=1 \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    GO_VERSION=1.20 \
    GO111MODULE=auto \
    GOARCH=amd64 \
    GOOS=linux \
    CGO_ENABLED=0 \
    NVD_EXCLUDE_TYPES="o,h" \
    PATH=/usr/local/src/:${PATH}:/opt/gradle/bin:/usr/local/go/bin:/opt/sl-cli:/opt/phpsast/vendor/bin:

COPY --from=builder /usr/local/bin/appthreat /usr/local/bin
COPY --from=builder /opt/pmd-bin-${PMD_VERSION} /opt/pmd-bin
COPY --from=builder /opt/spotbugs-${SB_VERSION} /opt/spotbugs
COPY --from=builder /opt/gradle-${GRADLE_VERSION} /opt/gradle
COPY . /usr/local/src/

USER root

RUN echo -e "[nodejs]\nname=nodejs\nstream=19\nprofiles=\nstate=enabled\n" > /etc/dnf/modules.d/nodejs.module \
    && microdnf install -y php php-curl php-zip php-bcmath php-json php-pear php-mbstring php-devel make gcc \
      findutils tar shadow-utils unzip zip sudo xz wget which maven \
      nodejs git-core java-11-openjdk-headless python3 python3-devel \
    && curl -LO "https://dl.google.com/go/go${GO_VERSION}.linux-amd64.tar.gz" \
    && tar -C /usr/local -xzf go${GO_VERSION}.linux-amd64.tar.gz \
    && rm go${GO_VERSION}.linux-amd64.tar.gz \
    && npm install --unsafe-perm -g yarn \
    && pecl channel-update pecl.php.net \
    && pecl install timezonedb \
    && echo 'extension=timezonedb.so' >> /etc/php.ini \
    && php -r "copy('https://getcomposer.org/installer', 'composer-setup.php');" && php composer-setup.php \
    && mv composer.phar /usr/local/bin/composer \
    && pip3 install --no-cache-dir poetry \
    && poetry config virtualenvs.create false \
    && cd /usr/local/src/ && poetry install --no-cache --without dev \
    && npm install --no-audit --progress=false --only=production -g @cyclonedx/cdxgen @microsoft/rush --unsafe-perm \
    && mkdir -p /opt/sl-cli /opt/phpsast && cd /opt/phpsast && composer require --quiet --no-cache --dev vimeo/psalm \
    && rm -rf /var/cache/yum \
    && microdnf remove -y python3-devel php-fpm php-devel php-pear automake make gcc gcc-c++ libtool \
    && microdnf clean all

WORKDIR /app

CMD [ "python3", "/usr/local/src/scan" ]

# 패키지 프록시 mirror 참고표

이 문서는 외부 public 저장소와 내부 proxy mirror 이름을 빠르게 찾기 위한 참고표입니다.
목록은 2026-07-08 사용자 제공 자료 기준이며, 같은 `type`과 `public`이 반복되는 항목은 원본 확인을 위해 그대로 보존했습니다.
환경별 적용 정책은 `docs/configuration.md`의 dependency source 정책을 기준으로 합니다.

## 사용 기준

- `type`: 저장소/패키지 생태계 종류입니다.
- `public`: 원본 외부 저장소 URL입니다.
- `mirror`: 내부 proxy mirror 저장소 이름입니다.
- 실제 접속 URL, 인증, 권한 정책은 운영 환경 설정을 따릅니다.

## 베이스 주소 패턴

현재 repo 설정에서 확인된 내부 베이스 주소는 아래와 같습니다.

| 대상 | 패턴 | 예시 |
| --- | --- | --- |
| Docker image | `repository.samsungds.net/<mirror>/<image>:<tag>` | `repository.samsungds.net/proxy-docker-registry-1.docker.io/apache/airflow:2.11.0` |
| Nexus repository 계열 | `http://repository.samsungds.net/repository/<mirror>` | `http://repository.samsungds.net/repository/proxy-apt-mirror.kakao.com-debian` |
| PyPI simple index | `http://repository.samsungds.net/repository/<mirror>/simple` | `http://repository.samsungds.net/repository/proxy-pypi-files.pythonhosted.org/simple` |
| Raw repository 계열 | `http://repository.samsungds.net/repository/<mirror>` | `http://repository.samsungds.net/repository/proxy-raw-dl-cdn.alpinelinux.org-alpine` |

확인된 repo 적용 사례는 `docs/configuration.md`의 사내 mirror 매핑을 기준으로 합니다.
`helm`, `maven2`, `conda`, `yum`, `cargo`, `conan`, `nuget`, `r`, `rubygems`, 일부 `raw` mirror는 이 repo 안에 실제 적용 예가 없으므로 운영 Nexus/Artifactory 설정에서 최종 베이스 주소를 확인해야 합니다.

## apt

| public | mirror |
| --- | --- |
| `https://download.docker.com/linux/ubuntu` | `proxy-apt-download.docker.com-linux-ubuntu` |
| `https://packages.cloud.google.com/apt/` | `proxy-apt-packages.cloud.google.com-apt` |
| `https://apt.kitware.com` | `proxy-apt-apt.kitware.com` |
| `https://artifacts.elastic.co` | `proxy-apt-artifacts.elastic.co` |
| `https://broadcom.jfrog.io/artifactory/vcfcli-debian/` | `proxy-apt-broadcom.jfrog.io-artifactory-vcfcli-debian` |
| `https://cli.github.com/` | `proxy-apt-cli.github.com` |
| `https://cli.github.com/` | `proxy-apt-cli.github.com` |
| `http://deb.debian.org/` | `proxy-apt-deb.debian.org` |
| `https://archive.ubuntu.com/ubuntu` | `proxy-apt-archive.ubuntu.com-ubuntu` |
| `http://download.ceph.com/` | `proxy-apt-download.ceph.com` |
| `http://ppa.launchpadcontent.net/deadsnakes/ppa/ubuntu/` | `proxy-apt-ppa.launchpadcontent.net-deadsnakes-ppa-ubuntu` |
| `https://download.docker.com/linux/debian` | `proxy-apt-download.docker.com-linux-debian` |
| `https://pkgs.k8s.io/core:/stable:` | `proxy-apt-pkgs.k8s.io-core-stable` |
| `http://ppa.launchpadcontent.net/maas/3.5/ubuntu` | `proxy-apt-ppa.launchpadcontent.net-maas-3.5-ubuntu` |
| `http://ppa.launchpadcontent.net/maas/3.6/ubuntu` | `proxy-apt-ppa.launchpadcontent.net-maas-3.6-ubuntu` |
| `https://linux.mellanox.com/public/repo/` | `proxy-apt-linux.mellanox.com-public-repo` |
| `http://mirror.kakao.com/debian/` | `proxy-apt-mirror.kakao.com-debian` |
| `https://provo-mirror.opensuse.org/` | `proxy-apt-provo-mirror.opensuse.org` |
| `https://packagecloud.io/allegro/ralph` | `proxy-apt-packagecloud.io-allegro-ralph` |
| `http://mirror.kakao.com/ubuntu/` | `proxy-apt-mirror.kakao.com-ubuntu` |
| `https://snapcraft.io/store` | `proxy-apt-snapcraft.io-store` |
| `http://ftp.kaist.ac.kr/debian/` | `proxy-apt-ftp.kaist.ac.kr-debian` |
| `http://ftp.kaist.ac.kr/ubuntu/` | `proxy-apt-ftp.kaist.ac.kr-ubuntu` |
| `https://images.maas.io/ephemeral-v3/stable` | `proxy-apt-images.maas.io-ephemeral-v3-stable` |
| `http://developer.download.nvidia.com/compute/cuda/repos/` | `proxy-apt-developer.download.nvidia.com-compute-cuda-repos` |
| `https://nvidia.github.io/nvidia-container-runtime` | `proxy-apt-nvidia.github.io-nvidia-container-runtime` |
| `http://pkg.jenkins.io/debian` | `proxy-apt-pkg.jenkins.io-debian` |
| `https://download.postgresql.org/pub/repos/apt/` | `proxy-apt-download.postgresql.org-pub-repos-apt` |
| `https://download.docker.com/linux/ubuntu` | `proxy-apt-download.docker.com-linux-ubuntu` |
| `http://archive.raspbian.org/raspbian/` | `proxy-apt-archive.raspbian.org-raspbian` |
| `http://packages.ros.org` | `proxy-apt-packages.ros.org` |
| `https://repo.scala-sbt.org` | `proxy-apt-repo.scala-sbt.org` |
| `http://ports.ubuntu.com/` | `proxy-apt-ports.ubuntu.com` |
| `https://repo.zabbix.com/zabbix/6.0/ubuntu` | `proxy-apt-repo.zabbix.com-zabbix-6.0-ubuntu` |

## cargo

| public | mirror |
| --- | --- |
| `https://index.crates.io/` | `proxy-cargo-index.crates.io` |

## conan

| public | mirror |
| --- | --- |
| `https://milvus01.jfrog.io/artifactory/api/conan/default-conan-local` | `proxy-conan-v1-milvus01.jfrog.io-default-conan-local` |
| `https://milvus01.jfrog.io/artifactory/api/conan/default-conan-local` | `proxy-conan-v2-milvus01.jfrog.io-default-conan-local` |
| `https://milvus01.jfrog.io/artifactory/api/conan/default-conan-local2` | `proxy-conan-v1-milvus01.jfrog.io-default-conan-local2` |
| `https://milvus01.jfrog.io/artifactory/api/conan/default-conan-local2` | `proxy-conan-v2-milvus01.jfrog.io-default-conan-local2` |

## conda

| public | mirror |
| --- | --- |
| `https://conda.anaconda.org/` | `proxy-conda-conda.anaconda.org` |
| `https://conda.anaconda.org/conda-forge` | `proxy-conda-conda.anaconda.org-conda-forge` |
| `https://conda.anaconda.org/nvidia` | `proxy-conda-conda.anaconda.org-nvidia` |
| `https://conda.anaconda.org/pytorch/` | `proxy-conda-conda.anaconda.org-pytorch` |
| `https://conda.anaconda.org/rapidsai` | `proxy-conda-conda.anaconda.org-rapidsai` |
| `https://conda.anaconda.org/ucb-bar` | `proxy-conda-conda.anaconda.org-ucb-bar` |
| `https://repo.continuum.io/pkgs/free/` | `proxy-conda-repo.continuum.io-pkgs-free` |

## docker

| public | mirror |
| --- | --- |
| `https://public.ecr.aws/` | `proxy-docker-public.ecr.aws` |
| `https://docker.bintray.io` | `proxy-docker-docker.bintray.io` |
| `https://projects.packages.broadcom.com` | `proxy-docker-projects.packages.broadcom.com` |
| `https://broadcom-vcf-cli-docker.jfrog.io` | `proxy-docker-broadcom-vcf-cli-docker.jfrog.io` |
| `https://broadcom-vcfa.jfrog.io` | `proxy-docker-broadcom-vcfa.jfrog.io` |
| `https://broadcom-vsphere-docker.jfrog.io` | `proxy-docker-broadcom-vsphere-docker.jfrog.io` |
| `https://container-registry.oracle.com` | `proxy-docker-container-registry.oracle.com` |
| `https://docker.elastic.co/` | `proxy-docker-docker.elastic.co` |
| `https://registry-1.docker.io/` | `proxy-docker-registry-1.docker.io` |
| `https://downloads.unstructured.io` | `proxy-docker-downloads.unstructured.io` |
| `https://gcr.io` | `proxy-docker-gcr.io` |
| `https://ghcr.io/` | `proxy-docker-ghcr.io` |
| `https://releases-docker.jfrog.io` | `proxy-docker-releases-docker.jfrog.io` |
| `https://registry.k8s.io/` | `proxy-docker-registry.k8s.io` |
| `https://k8s.gcr.io` | `proxy-docker-k8s.gcr.io` |
| `https://mcr.microsoft.com` | `proxy-docker-mcr.microsoft.com` |
| `https://nvcr.io/` | `proxy-docker-nvcr.io` |
| `https://registry-1.docker.io/` | `proxy-docker-registry-1.docker.io-proteantecs` |
| `https://public.ecr.aws` | `proxy-docker-public.ecr.aws` |
| `https://quay.io/` | `proxy-docker-quay.io` |
| `https://registry.k8s.io/` | `proxy-docker-registry.k8s.io` |

## go

| public | mirror |
| --- | --- |
| `https://proxy.golang.org` | `proxy-go-proxy.golang.org` |

## helm

| public | mirror |
| --- | --- |
| `https://airflow.apache.org/` | `proxy-helm-airflow.apache.org` |
| `https://charts.bitnami.com/bitnami` | `proxy-helm-charts.bitnami.com-bitnami` |

## maven2

| public | mirror |
| --- | --- |
| `https://packages.atlassian.com/mvn/maven-external/` | `proxy-maven2-packages.atlassian.com-mvn-maven-external` |
| `https://css4j.github.io/maven/` | `proxy-maven2-css4j.github.io-maven` |
| `https://plugins.gradle.org/` | `proxy-maven2-plugins.gradle.org` |
| `https://jcenter.bintray.com` | `proxy-maven2-jcenter.bintray.com` |
| `https://maven.google.com` | `proxy-maven2-maven.google.com` |
| `https://maven.anypoint.mulesoft.com/api/v3/maven` | `proxy-maven2-maven.anypoint.mulesoft.com-api-v3-maven` |
| `https://nexus.xwiki.org/nexus/` | `proxy-maven2-nexus.xwiki.org-nexus` |
| `https://repo1.maven.org/maven2/` | `proxy-maven2-repo1.maven.org-maven2` |
| `https://repo.spring.io/plugins-release/` | `proxy-maven2-repo.spring.io-plugins-release` |
| `https://maven.xwiki.org/releases/` | `proxy-maven2-maven.xwiki.org-releases` |

## npm

| public | mirror |
| --- | --- |
| `https://nexus.dev.morpheus.kr/repository/npm/` | `proxy-npm-nexus.dev.morpheus.kr-repository-npm` |
| `https://packages.morpheus.kr/repository/npm-release/` | `proxy-npm-packages.morpheus.kr-repository-npm-release` |
| `https://registry.npmjs.org` | `proxy-npm-registry.npmjs.org` |
| `https://registry.yarnpkg.com` | `proxy-npm-registry.yarnpkg.com` |

## nuget

| public | mirror |
| --- | --- |
| `https://www.nuget.org/` | `proxy-nuget-www.nuget.org` |

## pypi

| public | mirror |
| --- | --- |
| `https://pypi.nvidia.com/` | `proxy-pypi-pypi.nvidia.com` |
| `https://files.pythonhosted.org` | `proxy-pypi-files.pythonhosted.org` |
| `https://download.pytorch.org/whl/` | `proxy-pypi-download.pytorch.org-whl` |

## r

| public | mirror |
| --- | --- |
| `https://cran.r-project.org/` | `proxy-r-cran.r-project.org` |

## raw

| public | mirror |
| --- | --- |
| `https://dl-cdn.alpinelinux.org/alpine` | `proxy-raw-dl-cdn.alpinelinux.org-alpine` |
| `https://broadcom.jfrog.io/artifactory/photon/` | `proxy-raw-broadcom.jfrog.io-artifactory-photon` |
| `https://broadcom.jfrog.io/artifactory/vcf-distro` | `proxy-raw-broadcom.jfrog.io-artifactory-vcf-distro` |
| `https://dl.k8s.io` | `proxy-raw-dl.k8s.io` |
| `https://developer.download.nvidia.com/compute/cuda/` | `proxy-raw-developer.download.nvidia.com-compute-cuda` |
| `https://dl.google.com/android/repository` | `proxy-raw-dl.google.com-android-repository` |
| `https://developer.download.nvidia.com/compute/redist/gdrcopy` | `proxy-raw-developer.download.nvidia.com-compute-redist-gdrcopy` |
| `https://github.com/electron/electron/releases/download` | `proxy-raw-github.com-electron-electron-releases-download` |
| `https://github.com/indygreg` | `proxy-raw-github.com-indygreg` |
| `https://github.com/` | `proxy-raw-github.com` |
| `https://download.ni.com` | `proxy-raw-download.ni.com` |
| `https://data.pyg.org` | `proxy-raw-data.pyg.org` |
| `https://downloads.python.org` | `proxy-raw-downloads.python.org` |
| `https://provo-mirror.opensuse.org/` | `proxy-raw-provo-mirror.opensuse.org` |
| `https://dl.google.com/dl/android/maven2/` | `proxy-raw-dl.google.com-dl-android-maven2` |
| `https://pkgs.k8s.io/` | `proxy-raw-pkgs.k8s.io` |
| `https://nvidia.github.io/libnvidia-container` | `proxy-raw-nvidia.github.io-libnvidia-container` |
| `https://repository.mulesoft.org/releases/` | `proxy-raw-repository.mulesoft.org-releases` |
| `https://nvidia.github.io/nvidia-container-runtime/` | `proxy-raw-nvidia.github.io-nvidia-container-runtime` |
| `https://developer.download.nvidia.com/compute/cuda/repos/` | `proxy-raw-developer.download.nvidia.com-compute-cuda-repos` |
| `https://open-vsx.org/` | `proxy-raw-open-vsx.org` |
| `https://packages.microsoft.com/` | `proxy-raw-packages.microsoft.com` |
| `https://pkgs.k8s.io/core:/stable:` | `proxy-raw-pkgs.k8s.io-core-stable` |
| `https://storage.googleapis.com` | `proxy-raw-storage.googleapis.com` |
| `http://download.tizen.org/` | `proxy-raw-download.tizen.org` |
| `https://ftp.kaist.ac.kr/ubuntu-cd/` | `proxy-raw-ftp.kaist.ac.kr-ubuntu-cd` |
| `https://github.com/astral-sh/python-build-standalone/releases/download` | `proxy-raw-github.com-astral-sh-python-build-standalone-releases-download` |
| `https://wp-content.vmware.com/` | `proxy-raw-wp-content.vmware.com` |

## rubygems

| public | mirror |
| --- | --- |
| `https://rubygems.org/` | `proxy-rubygems-rubygems.org` |

## yum

| public | mirror |
| --- | --- |
| `https://cdn.redhat.com/content/dist/layered/rhel8/x86_64/ansible/2.9/os` | `proxy-yum-cdn.redhat.com-content-dist-layered-rhel8-x86_64-ansible-2.9-os` |
| `https://repos.azul.com/zulu/rpm` | `proxy-yum-repos.azul.com-zulu-rpm` |
| `https://broadcom.jfrog.io/artifactory/vcfcli-rpm/` | `proxy-yum-broadcom.jfrog.io-artifactory-vcfcli-rpm` |
| `http://mirror.stream.centos.org/9-stream/` | `proxy-yum-mirror.stream.centos.org-9-stream` |
| `https://vault.centos.org/` | `proxy-yum-vault.centos.org` |
| `https://cdn.redhat.com/content/dist/rhel8/8/x86_64/codeready-builder/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel8-8-x86_64-codeready-builder-os` |
| `https://cdn.redhat.com/content/dist/rhel9/9/aarch64/codeready-builder/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel9-9-aarch64-codeready-builder-os` |
| `https://cdn.redhat.com/content/dist/rhel9/9/x86_64/codeready-builder/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel9-9-x86_64-codeready-builder-os` |
| `https://packages.confluent.io/` | `proxy-yum-packages.confluent.io` |
| `https://packages.daos.io/` | `proxy-yum-packages.daos.io` |
| `https://cdn.redhat.com/content/dist/layered/rhel8/x86_64/fast-datapath/os` | `proxy-yum-cdn.redhat.com-content-dist-layered-rhel8-x86_64-fast-datapath-os` |
| `https://dl.fedoraproject.org/pub/archive/epel/` | `proxy-yum-dl.fedoraproject.org-pub-archive-epel` |
| `https://dl.fedoraproject.org/pub/fedora` | `proxy-yum-dl.fedoraproject.org-pub-fedora` |
| `https://dl.fedoraproject.org/pub/epel/` | `proxy-yum-dl.fedoraproject.org-pub-epel` |
| `https://dl.fedoraproject.org/pub/archive/fedora/` | `proxy-yum-dl.fedoraproject.org-pub-archive-fedora` |
| `https://releases.jfrog.io/artifactory/jfrog-rpms` | `proxy-yum-releases.jfrog.io-artifactory-jfrog-rpms` |
| `http://ftp.kaist.ac.kr/opensuse/` | `proxy-yum-ftp.kaist.ac.kr-opensuse` |
| `https://al2023-repos-ap-northeast-2-de612dc2.s3.dualstack.ap-northeast-2.amazonaws.com` | `proxy-yum-al2023-repos-ap-northeast-2-de612dc2.s3.dualstack.ap-northeast-2.amazonaws.com` |
| `https://yum.oracle.com/repo/OracleLinux/` | `proxy-yum-yum.oracle.com-repo-oraclelinux` |
| `https://mirror.stream.centos.org/10-stream/` | `proxy-yum-mirror.stream.centos.org-10-stream` |
| `https://nvidia.github.io/nvidia-docker` | `proxy-yum-nvidia.github.io-nvidia-docker` |
| `https://nvidia.github.io/libnvidia-container/` | `proxy-yum-nvidia.github.io-libnvidia-container` |
| `https://artifacts.opensearch.org/` | `proxy-yum-artifacts.opensearch.org` |
| `https://cdn.redhat.com/content/dist/layered/rhel8/x86_64/openstack/16.2/os` | `proxy-yum-cdn.redhat.com-content-dist-layered-rhel8-x86_64-openstack-16.2-os` |
| `https://www.pgpool.net/yum/` | `proxy-yum-www.pgpool.net-yum` |
| `http://pkg.jenkins.io/redhat-stable` | `proxy-yum-pkg.jenkins.io-redhat-stable` |
| `https://download.postgresql.org/pub/repos/yum/` | `proxy-yum-download.postgresql.org-pub-repos-yum` |
| `https://repo.radeon.com` | `proxy-yum-repo.radeon.com` |
| `https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel-server-7-7Server-x86_64-os` |
| `https://cdn.redhat.com/content/dist/rhel8/8/x86_64/appstream/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel8-8-x86_64-appstream-os` |
| `https://cdn.redhat.com/content/dist/rhel8/8/x86_64/baseos/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel8-8-x86_64-baseos-os` |
| `https://cdn.redhat.com/content/eus/rhel8/8.4/x86_64/highavailability/os` | `proxy-yum-cdn.redhat.com-content-eus-rhel8-8.4-x86_64-highavailability-os` |
| `https://cdn.redhat.com/content/eus/rhel8/8.4/x86_64/appstream/os` | `proxy-yum-cdn.redhat.com-content-eus-rhel8-8.4-x86_64-appstream-os` |
| `https://cdn.redhat.com/content/eus/rhel8/8.4/x86_64/baseos/os` | `proxy-yum-cdn.redhat.com-content-eus-rhel8-8.4-x86_64-baseos-os` |
| `https://cdn.redhat.com/content/eus/rhel8/8.6/x86_64/appstream/os` | `proxy-yum-cdn.redhat.com-content-eus-rhel8-8.6-x86_64-appstream-os` |
| `https://cdn.redhat.com/content/eus/rhel8/8.6/x86_64/baseos/os` | `proxy-yum-cdn.redhat.com-content-eus-rhel8-8.6-x86_64-baseos-os` |
| `https://cdn.redhat.com/content/eus/rhel8/8.8/x86_64/appstream/os` | `proxy-yum-cdn.redhat.com-content-eus-rhel8-8.8-x86_64-appstream-os` |
| `https://cdn.redhat.com/content/eus/rhel8/8.8/x86_64/baseos/os` | `proxy-yum-cdn.redhat.com-content-eus-rhel8-8.8-x86_64-baseos-os` |
| `https://cdn.redhat.com/content/dist/rhel8/8.10/x86_64/appstream/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel8-8.10-x86_64-appstream-os` |
| `https://cdn.redhat.com/content/dist/rhel8/8.10/x86_64/baseos/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel8-8.10-x86_64-baseos-os` |
| `https://cdn.redhat.com/content/dist/rhel9/9/x86_64/appstream/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel9-9-x86_64-appstream-os` |
| `https://cdn.redhat.com/content/dist/rhel9/9/x86_64/baseos/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel9-9-x86_64-baseos-os` |
| `https://cdn.redhat.com/content/eus/rhel9/9.2/x86_64/appstream/os` | `proxy-yum-cdn.redhat.com-content-eus-rhel9-9.2-x86_64-appstream-os` |
| `https://cdn.redhat.com/content/eus/rhel9/9.2/x86_64/baseos/os` | `proxy-yum-cdn.redhat.com-content-eus-rhel9-9.2-x86_64-baseos-os` |
| `https://cdn.redhat.com/content/eus/rhel9/9.4/x86_64/appstream/os` | `proxy-yum-cdn.redhat.com-content-eus-rhel9-9.4-x86_64-appstream-os` |
| `https://cdn.redhat.com/content/eus/rhel9/9.4/x86_64/baseos/os` | `proxy-yum-cdn.redhat.com-content-eus-rhel9-9.4-x86_64-baseos-os` |
| `https://cdn.redhat.com/content/dist/rhel9/9.6/aarch64/appstream/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel9-9.6-aarch64-appstream-os` |
| `https://cdn.redhat.com/content/dists/rhel9/9.6/aarch64/baseos/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel9-9.6-aarch64-baseos-os` |
| `https://cdn.redhat.com/content/eus/rhel9/9.6/x86_64/appstream/os` | `proxy-yum-cdn.redhat.com-content-eus-rhel9-9.6-x86_64-appstream-os` |
| `https://cdn.redhat.com/content/eus/rhel9/9.6/x86_64/baseos/os` | `proxy-yum-cdn.redhat.com-content-eus-rhel9-9.6-x86_64-baseos-os` |
| `https://cdn.redhat.com/content/dist/rhel10/10.0/x86_64/appstream/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel10-10.0-x86_64-appstream-os` |
| `https://cdn.redhat.com/content/dist/rhel10/10.0/x86_64/baseos/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel10-10.0-x86_64-baseos-os` |
| `https://dl.rockylinux.org/vault/rocky/` | `proxy-yum-dl.rockylinux.org-vault-rocky` |
| `http://download.ceph.com/` | `proxy-yum-download.ceph.com` |
| `https://cli.github.com/` | `proxy-yum-cli.github.com` |
| `http://mirror.kakao.com/epel/` | `proxy-yum-mirror.kakao.com-epel` |
| `https://cli.github.com/` | `proxy-yum-cli.github.com` |
| `http://mirror.kakao.com/centos/` | `proxy-yum-mirror.kakao.com-centos` |
| `http://mirror.kakao.com/opensuse/` | `proxy-yum-mirror.kakao.com-opensuse` |
| `https://mirror.navercorp.com/rocky/` | `proxy-yum-mirror.navercorp.com-rocky` |
| `https://download.docker.com/linux/centos` | `proxy-yum-download.docker.com-linux-centos` |
| `https://packages.cloud.google.com/yum/` | `proxy-yum-packages.cloud.google.com-yum` |
| `https://pkgs.k8s.io/` | `proxy-yum-pkgs.k8s.io` |
| `https://linux.mellanox.com/public/repo/` | `proxy-yum-linux.mellanox.com-public-repo` |
| `https://provo-mirror.opensuse.org/` | `proxy-yum-provo-mirror.opensuse.org` |
| `https://download.docker.com/linux/rhel` | `proxy-yum-download.docker.com-linux-rhel` |
| `https://repo.zabbix.com/` | `proxy-yum-repo.zabbix.com` |
| `https://repo.zabbix.com/zabbix/5.0/rhel/7/` | `proxy-yum-repo.zabbix.com-zabbix-5.0-rhel-7` |

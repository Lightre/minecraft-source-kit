# Third-party notices

The GPL-3.0-only license in [LICENSE](LICENSE) covers this kit's original files. It does not replace licenses or permissions for external software or Minecraft materials.

## CFR

The kit fetches and builds CFR from its official repository at revision `c4145259dfcd8ad3e99004e4d9ecb0aed55dcc5a`. CFR uses the MIT License, with the upstream notice: Copyright (c) 2011-2019 Lee Benfield.

- Upstream: https://github.com/leibnitz27/cfr
- Pinned license: https://github.com/leibnitz27/cfr/blob/c4145259dfcd8ad3e99004e4d9ecb0aed55dcc5a/LICENSE

CFR runs as an external process. Its source checkout, license, and built JAR remain in ignored local tool storage and are not included in the kit repository. Separate redistribution must retain its upstream license and notices.

## Vineflower

Optional per-class recovery downloads Vineflower 1.12.0 from its official release. Vineflower uses the Apache License, Version 2.0.

- Release: https://github.com/Vineflower/vineflower/releases/tag/1.12.0
- Pinned license: https://github.com/Vineflower/vineflower/blob/1.12.0/LICENSE.md

Vineflower runs as an external process. Its downloaded JAR remains in ignored local tool storage and is not included in the kit repository. Separate redistribution must comply with its upstream license, including applicable notice requirements.

## Minecraft and target projects

Minecraft JARs are supplied by the user. JARs, reconstructed Java files, and reference caches are not included in the kit repository or licensed by this project. Users must obtain and use Minecraft materials under the applicable terms from their rights holders:

- Minecraft EULA: https://www.minecraft.net/en-us/eula
- Minecraft usage guidelines: https://www.minecraft.net/en-us/usage-guidelines

The kit grants no additional permission to redistribute Minecraft materials. An independent mod project does not become GPL-licensed merely because its developer uses this kit. Copying kit code or documentation into another distributed work is a separate licensing matter.

## Other prerequisites

Python, Git, and a JDK are installed separately and retain the terms of their respective distributions. The kit does not bundle these runtimes or development tools.

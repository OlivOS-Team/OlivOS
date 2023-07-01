name: Bug report
description: Create a report to help us improve
title: "我发现了一个潜在的漏洞并希望官方能够修复它"
labels: [bug]
body:
  - type: input
    id: describe
    attributes:
      label: Describe
      placeholder: Describe the bug
    validations:
      required: true
  - type: textarea
    id: deproduce
    attributes:
      label: To Reproduce
      placeholder: |
        Steps to reproduce the behavior:
        1. Go to '...'
        2. Click on '....'
        3. Scroll down to '....'
        4. See error
    validations:
      required: false
  - type: textarea
    id: expected_behavior
    attributes:
      label: Expected behavior
      description: A clear and concise description of what you expected to happen.
    validations:
      required: false
  - type: textarea
    id: screenshots
    attributes:
      label: Screenshots
      description: If applicable, add screenshots to help explain your problem.
    validations:
      required: false
  - type: textarea
    id: desktop
    attributes:
      label: Desktop (please complete the following information)
      description: |
         - OS: [e.g. iOS]
         - Browser [e.g. chrome, safari]
         - Version [e.g. 22]
    validations:
      required: true
  - type: textarea
    id: smartphone
    attributes:
      label: Smartphone (please complete the following information)
      description: |
         - Device: [e.g. iPhone6]
         - OS: [e.g. iOS8.1]
         - Browser [e.g. stock browser, safari]
         - Version [e.g. 22]
    validations:
      required: true
  - type: textarea
    id: expected_behavior
    attributes:
      label: Additional context
      description: Add any other context about the problem here.
    validations:
      required: true
  - type: markdown
    attributes:
      value: |
        你也可以加入[用户2群【OlivOS青果铺｜用户交流】](http://qm.qq.com/cgi-bin/qm/qr?_wv=1027&k=Xb0LXu7ZCSopSOxwM0CSQCLhlS_TF21H&authKey=gN5E07ZNJ3MjST1AuyTxZLqdMoH3rwNWASRMUQJ%2BcMBG9vMWRElJxM3RspQjZeYp&noverify=0&group_code=635811009)或者[论坛](forum.olivos.run)获取更多信息。

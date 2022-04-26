<p align="center">
  <a href="#">
    <img src="https://raw.githubusercontent.com/OlivOS-Team/OlivOS/main/resource/OlivOS_EA_SIP.jpg" width="384" height="216" alt="">
  </a>
</p>

<div align="center">

# OlivOS

**青果核心交互栈**  
**Witness Union / 见证联合**  

  <a href="https://github.com/botuniverse/onebot">
    <img src="https://img.shields.io/badge/OneBot-v11-black?logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAHAAAABwCAMAAADxPgR5AAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAAAxQTFRF////29vbr6+vAAAAk1hCcwAAAAR0Uk5T////AEAqqfQAAAKcSURBVHja7NrbctswDATQXfD//zlpO7FlmwAWIOnOtNaTM5JwDMa8E+PNFz7g3waJ24fviyDPgfhz8fHP39cBcBL9KoJbQUxjA2iYqHL3FAnvzhL4GtVNUcoSZe6eSHizBcK5LL7dBr2AUZlev1ARRHCljzRALIEog6H3U6bCIyqIZdAT0eBuJYaGiJaHSjmkYIZd+qSGWAQnIaz2OArVnX6vrItQvbhZJtVGB5qX9wKqCMkb9W7aexfCO/rwQRBzsDIsYx4AOz0nhAtWu7bqkEQBO0Pr+Ftjt5fFCUEbm0Sbgdu8WSgJ5NgH2iu46R/o1UcBXJsFusWF/QUaz3RwJMEgngfaGGdSxJkE/Yg4lOBryBiMwvAhZrVMUUvwqU7F05b5WLaUIN4M4hRocQQRnEedgsn7TZB3UCpRrIJwQfqvGwsg18EnI2uSVNC8t+0QmMXogvbPg/xk+Mnw/6kW/rraUlvqgmFreAA09xW5t0AFlHrQZ3CsgvZm0FbHNKyBmheBKIF2cCA8A600aHPmFtRB1XvMsJAiza7LpPog0UJwccKdzw8rdf8MyN2ePYF896LC5hTzdZqxb6VNXInaupARLDNBWgI8spq4T0Qb5H4vWfPmHo8OyB1ito+AysNNz0oglj1U955sjUN9d41LnrX2D/u7eRwxyOaOpfyevCWbTgDEoilsOnu7zsKhjRCsnD/QzhdkYLBLXjiK4f3UWmcx2M7PO21CKVTH84638NTplt6JIQH0ZwCNuiWAfvuLhdrcOYPVO9eW3A67l7hZtgaY9GZo9AFc6cryjoeFBIWeU+npnk/nLE0OxCHL1eQsc1IciehjpJv5mqCsjeopaH6r15/MrxNnVhu7tmcslay2gO2Z1QfcfX0JMACG41/u0RrI9QAAAABJRU5ErkJggg==" alt="action">
  </a>
  <a href="https://github.com/OlivOS-Team/OlivOS/actions">
    <img src="https://github.com/OlivOS-Team/OlivOS/workflows/CI-Packing/badge.svg" alt="action">
  </a>
  <a href="https://pypi.python.org/pypi/olivos">
    <img src="https://img.shields.io/pypi/v/olivos" alt="PyPI">
  </a>
  <a href="https://github.com/OlivOS-Team/OlivOS/releases">
    <img src="https://img.shields.io/github/downloads/OlivOS-Team/OlivOS/total.svg" alt="Downloads">
  </a>

  <p align="center">
    <a href="https://doc.olivos.wiki/">文档</a>
    ·
    <a href="https://github.com/OlivOS-Team/OlivOS/releases">下载</a>
  </p>

</div>

## 兼容
[![QQGuild](https://img.shields.io/badge/-QQGuild-EB1923?style=flat-square&logo=Tencent%20QQ&logoColor=white)](https://bot.q.qq.com/wiki/)
[![Onebot](https://img.shields.io/badge/-Onebot-EB1923?style=flat-square&logo=Tencent%20QQ&logoColor=white)](https://github.com/botuniverse/onebot)
[![Go-CQHttp](https://img.shields.io/badge/-GoCQHttp-EB1923?style=flat-square&logo=Tencent%20QQ&logoColor=white)](https://github.com/Mrs4s/go-cqhttp)
[![Telegram](https://img.shields.io/badge/-Telegram-26A5E4?style=flat-square&logo=Telegram&logoColor=white)](https://telegram.org/)
[![开黑啦](https://img.shields.io/badge/-%E5%BC%80%E9%BB%91%E5%95%A6-6666CC?style=flat-square&logo=Discord&logoColor=white)](https://www.kaiheila.cn/)
[![Dodo](https://img.shields.io/badge/-Dodo-00B8AA?style=flat-square&logo=%2Fe%2F&logoColor=white)](https://dodo.link/)
[![Fanbook](https://img.shields.io/badge/-Fanbook-1A52F3?style=flat-square&logo=sharp&logoColor=white)](https://fanbook.mobi/)

> *排名不分先后*

## 概述
**OlivOS 青果核心交互栈**，一个将各类涉及异步文本流交互的场景（即时通讯、直播弹幕、网络聊天室、静态命令行应用程序）转换到统一框架，基于统一流量管理、负载均衡、业务处理机制进行服务，以期在这些交互逻辑与功能需求类似的场景获得**更加灵活的部署方式**、**更加有效的开发模式**以及**更加合理的资源调度**。  

## 方针
技术路线上，基于Python、采用模块化框架、进程分离、消息队列通信、前后端分离、响应式布局、渐进式渲染的基本思路，实现一个高并发性、高可靠性、高适应性的整体方案。

## 插件
请参考插件默认模板[OlivOSPluginTemplate](https://github.com/OlivOS-Team/OlivOSPluginTemplate)和[官方文档](https://doc.olivos.wiki)进行插件开发。

## 开始使用
请参考[启程手册](https://wiki.dice.center/OlivOS_Login.html)进行OlivOS的首次使用

## 许可证

    Copyright (C) 2019-2021 lunzhiPenxil and OlivOS Team and contributors.

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, either version 3 of the
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

`OlivOS` 采用 `AGPLv3` 协议开源。为了整个社区的良性发展，我们**强烈建议**您做到以下几点：

- **间接接触（包括但不限于使用 `Http API` 或 跨进程技术）到 `OlivOS` 的软件使用 `AGPLv3` 开源**

### **OlivOS 的形象图及项目图标都拥有著作权保护。**
**在未经过允许的情况下，任何人都不可以使用形象图和图标，或本文初的有关 OlivOS 名称来历的介绍原文，用于商业用途或是放置在项目首页，或其他未许可的行为。**

### 衍生软件需声明引用

- 若引用 OlivOS 发布的软件包而不修改 OlivOS，则衍生项目需在描述的任意部位提及使用 OlivOS。
- 若修改 OlivOS 源代码再发布，**或参考 OlivOS 内部实现发布另一个项目**，则衍生项目必须在**文章首部**或 'OlivOS' 相关内容**首次出现**的位置**明确声明**来源于本仓库 (`https://github.com/OlivOS-Team/OlivOS`)。不得扭曲或隐藏免费且开源的事实。

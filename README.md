# SIGET

## Sistema Integral de Gestión de Equipos y Soporte Tecnológico

## Desarrollo realizado con

- ![Visual Studio Code](https://img.shields.io/badge/Visual%20Studio%20Code-0078d7.svg?style=for-the-badge&logo=visual-studio-code&logoColor=white)

## Sistemas operativos utilizados

- ![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)
- ![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)

## Tecnologías utilizadas

- ![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
- ![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white)
- ![Django REST Framework](https://img.shields.io/badge/Django%20REST%20Framework-A30000?style=for-the-badge&logo=django&logoColor=white)
- ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
- ![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)
- ![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)
- ![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)
- ![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
- ![Docker Compose](https://img.shields.io/badge/Docker%20Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)
- ![Git](https://img.shields.io/badge/Git-F05032?style=for-the-badge&logo=git&logoColor=white)
- ![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)

## Framework para aplicación de escritorio

- ![PySide6](https://img.shields.io/badge/PySide6-41CD52?style=for-the-badge&logo=qt&logoColor=white)

## Descripción

**SIGET** es un Sistema Integral de Gestión de Equipos y Soporte Tecnológico diseñado para centralizar la administración de activos TI y los procesos de soporte técnico dentro de una organización.

La solución busca mejorar el control, seguimiento y trazabilidad de los equipos tecnológicos, permitiendo gestionar solicitudes, asignaciones, devoluciones, estados, reparaciones y tickets de soporte mediante un modelo de **Service Desk o Mesa de Ayuda**.

SIGET estará compuesto por una **Plataforma Web** destinada principalmente a colaboradores y una **Aplicación de Escritorio** orientada a técnicos TI y administradores.

Ambas aplicaciones se comunicarán mediante servicios REST desarrollados con **Django REST Framework**, utilizando una base de datos relacional **PostgreSQL**.

## Objetivo

Desarrollar una solución que permita centralizar y administrar la información relacionada con los equipos tecnológicos y los procesos de soporte TI de una organización, mejorando el control, la trazabilidad y el seguimiento de los activos y solicitudes de los usuarios.

## Componentes principales

### Plataforma Web

La Plataforma Web estará orientada principalmente a los colaboradores de la organización.

Permitirá:

- Iniciar sesión.
- Recuperar contraseña.
- Consultar equipos asignados.
- Visualizar información e historial de los equipos.
- Realizar solicitudes de equipos.
- Consultar el estado de las solicitudes.
- Crear tickets de soporte.
- Consultar y responder mensajes de tickets.
- Revisar notificaciones.
- Consultar información del perfil.

### Aplicación de Escritorio

La Aplicación de Escritorio estará orientada principalmente a técnicos TI y administradores.

Permitirá:

- Administrar activos tecnológicos.
- Gestionar solicitudes de equipos.
- Aprobar o rechazar solicitudes.
- Gestionar asignaciones.
- Registrar devoluciones.
- Actualizar estados de los equipos.
- Consultar trazabilidad.
- Gestionar tickets de soporte.
- Registrar diagnósticos y reparaciones.
- Gestionar mantenimientos.
- Administrar usuarios, roles y permisos.
- Consultar reportes y registros de auditoría.

### Backend / API REST

El backend será desarrollado utilizando **Python, Django y Django REST Framework**.

Será responsable de:

- Centralizar la lógica de negocio.
- Gestionar la autenticación.
- Administrar los datos del sistema.
- Permitir la comunicación entre la Plataforma Web y la Aplicación de Escritorio.
- Gestionar solicitudes, activos, tickets, notificaciones y demás módulos de SIGET.

### Base de Datos

SIGET utilizará **PostgreSQL** como sistema gestor de base de datos relacional.

La base de datos almacenará información relacionada con:

- Usuarios.
- Roles y permisos.
- Activos tecnológicos.
- Solicitudes.
- Asignaciones.
- Devoluciones.
- Estados de equipos.
- Tickets.
- Mensajes de tickets.
- Reparaciones.
- Mantenimientos.
- Repuestos.
- Notificaciones.
- Auditoría.
- Historial y trazabilidad.

## Módulos principales

- Gestión de usuarios y autenticación.
- Gestión de activos tecnológicos.
- Gestión de solicitudes y asignaciones.
- Gestión de devoluciones y trazabilidad.
- Gestión de tickets de soporte.
- Gestión de reparación y mantenimiento.
- Gestión de repuestos e insumos técnicos.
- Integración de APIs y seguridad.
- Auditoría y reportes.
- Notificaciones y seguimiento.

## Arquitectura general

```text
Plataforma Web
      |
      | REST API
      v
Backend Django / DRF
      |
      v
PostgreSQL
      ^
      |
      | REST API
      |
Aplicación de Escritorio

# File Transfer

## Introduction

This project consists of the development of a client-server file transfer system with reliable data transmission (RDT) mechanisms. It was created as a university group assignment by a team of five students, including myself.

The goal was to implement a file upload and download service that ensures reliable delivery over an unreliable transport protocol. The system supports two variants of the UDP-based protocol: Stop & Wait and Selective Repeat. The implementation includes custom handling for packet loss, retransmission, and acknowledgment, following the principles of RDT to guarantee correct data delivery.

The project repository includes a fully self-documented codebase. Each function, key variable declaration, and relevant logic is thoroughly commented to clarify the behavior and reasoning behind every component of the system.

A clarification: The project was developed for the University, so all analysis, code, and documentation are written in Spanish.

With this context in mind, let's move on to the explanation of the system's design and implementation strategy.

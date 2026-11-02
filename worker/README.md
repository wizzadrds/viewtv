# Worker

Proceso independiente para trabajos asíncronos, programado con APScheduler.

La cola será persistente en SQLite. Los trabajos usarán leases con vencimiento y heartbeat para poder recuperarse tras reinicios. El worker no debe depender de que la interfaz web permanezca abierta.

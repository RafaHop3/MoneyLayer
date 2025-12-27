def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            compare_type=True,
            # ADICIONE ESTA LINHA ABAIXO:
            render_as_batch=True  
        )

        with context.begin_transaction():
            context.run_migrations()
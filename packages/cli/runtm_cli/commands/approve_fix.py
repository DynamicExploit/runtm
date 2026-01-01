    # Create new manifest with ALL changes together (features + env_vars)
    # This avoids validation errors from partial updates (e.g., auth=True without AUTH_SECRET)
    if feature_changes or added_env:
        manifest = Manifest(
            name=manifest.name,
            template=manifest.template,
            runtime=manifest.runtime,
            health_path=manifest.health_path,
            port=manifest.port,
            tier=manifest.tier,
            features=merged_features,
            volumes=manifest.volumes,
            env_schema=merged_env,
            connections=manifest.connections,
            policy=manifest.policy,
        )
        if feature_changes:
            changes_made.append(f"Updated features: {', '.join(feature_changes)}")
        if added_env:
            changes_made.append(f"Added {len(added_env)} env vars: {', '.join(added_env)}")


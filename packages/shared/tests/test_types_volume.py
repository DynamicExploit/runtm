"""Tests for VolumeConfig in types."""

import pytest

from runtm_shared.types import MachineTier, MachineConfig, VolumeConfig


class TestVolumeConfig:
    """Test the VolumeConfig dataclass."""

    def test_create_volume_config(self):
        """Can create VolumeConfig."""
        vol = VolumeConfig(name="data", path="/data", size_gb=1)
        assert vol.name == "data"
        assert vol.path == "/data"
        assert vol.size_gb == 1

    def test_volume_config_default_size(self):
        """VolumeConfig has default size of 1GB."""
        vol = VolumeConfig(name="data", path="/data")
        assert vol.size_gb == 1


class TestMachineConfigWithVolumes:
    """Test MachineConfig with volumes."""

    def test_machine_config_no_volumes_by_default(self):
        """MachineConfig has empty volumes by default."""
        config = MachineConfig(image="test:latest")
        assert config.volumes == []

    def test_machine_config_with_volumes(self):
        """MachineConfig can have volumes."""
        volumes = [
            VolumeConfig(name="data", path="/data", size_gb=1),
            VolumeConfig(name="cache", path="/cache", size_gb=5),
        ]
        config = MachineConfig(image="test:latest", volumes=volumes)
        assert len(config.volumes) == 2
        assert config.volumes[0].name == "data"
        assert config.volumes[1].name == "cache"

    def test_from_tier_with_volumes(self):
        """MachineConfig.from_tier works with volumes."""
        volumes = [VolumeConfig(name="data", path="/data", size_gb=1)]
        config = MachineConfig.from_tier(
            tier=MachineTier.STANDARD,
            image="test:latest",
            volumes=volumes,
        )
        assert config.memory_mb == 512
        assert len(config.volumes) == 1
        assert config.volumes[0].name == "data"

    def test_from_tier_default_no_volumes(self):
        """MachineConfig.from_tier defaults to no volumes."""
        config = MachineConfig.from_tier(
            tier=MachineTier.STANDARD,
            image="test:latest",
        )
        assert config.volumes == []


#!/usr/bin/env python3
"""
DBC Generator for Data Acquisition Modules

Parses TOML configuration files and generates CAN DBC files.
Designed to be extensible for new sensor types.
"""

import tomllib
import argparse
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# =============================================================================
# Sensor Archetypes Registry
# =============================================================================

class SensorArchetype(ABC):
    """Base class for sensor archetypes. Subclass this to add new sensor types."""
    
    # Define required parameters for this sensor type (beyond common params)
    REQUIRED_PARAMS: list[str] = []
    
    # Define optional parameters with defaults
    OPTIONAL_PARAMS: dict[str, Any] = {}
    
    @classmethod
    @abstractmethod
    def sensor_type(cls) -> str:
        """Return the type identifier used in TOML config."""
        pass
    
    @classmethod
    def validate(cls, sensor_config: dict, sensor_index: int) -> list[str]:
        """Validate sensor-specific parameters. Returns list of error messages."""
        errors = []
        for param in cls.REQUIRED_PARAMS:
            if param not in sensor_config:
                errors.append(
                    f"Sensor {sensor_index} (type={cls.sensor_type()}): "
                    f"missing required parameter '{param}'"
                )
        return errors
    
    @classmethod
    def get_dbc_params(cls, sensor_config: dict) -> dict:
        """
        Extract DBC-relevant parameters from sensor config.
        Override this to customize DBC signal generation for this sensor type.
        """
        return {}


class ThermistorSensor(SensorArchetype):
    """Thermistor sensor using Steinhart-Hart equation."""
    
    REQUIRED_PARAMS = ["A", "B", "C", "pull_up"]
    OPTIONAL_PARAMS = {
        "A": None,
        "B": None,
        "C": None,
        "pull_up": None,
    }
    
    @classmethod
    def sensor_type(cls) -> str:
        return "thermistor"
    
    @classmethod
    def get_dbc_params(cls, sensor_config: dict) -> dict:
        return {
            "unit": "degC",
            "min_val": -40.0,
            "max_val": 150.0,
        }


class AnalogSensor(SensorArchetype):
    """Generic analog voltage sensor."""
    
    REQUIRED_PARAMS = []
    OPTIONAL_PARAMS = {
        "min_voltage": 0.0,
        "max_voltage": 5.0,
    }
    
    @classmethod
    def sensor_type(cls) -> str:
        return "analog"
    
    @classmethod
    def get_dbc_params(cls, sensor_config: dict) -> dict:
        return {
            "unit": "V",
            "min_val": sensor_config.get("min_voltage", 0.0),
            "max_val": sensor_config.get("max_voltage", 5.0),
        }


class DigitalSensor(SensorArchetype):
    """Digital input sensor."""
    
    REQUIRED_PARAMS = []
    OPTIONAL_PARAMS = {}
    
    @classmethod
    def sensor_type(cls) -> str:
        return "digital"
    
    @classmethod
    def get_dbc_params(cls, sensor_config: dict) -> dict:
        return {
            "unit": "",
            "min_val": 0,
            "max_val": 1,
        }


# -----------------------------------------------------------------------------
# Register all sensor archetypes here
# To add a new sensor type:
#   1. Create a new class inheriting from SensorArchetype
#   2. Add it to this dictionary
# -----------------------------------------------------------------------------
SENSOR_ARCHETYPES: dict[str, type[SensorArchetype]] = {
    "thermistor": ThermistorSensor,
    "analog": AnalogSensor,
    "digital": DigitalSensor,
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ModuleConfig:
    """Module-level configuration."""
    identifier: str
    func_grp: int
    rtos_tick_hz: int = 1000


@dataclass
class SensorConfig:
    """Sensor configuration with common and type-specific params."""
    name: str
    sensor_type: str
    offset: float = 0.0
    scale: float = 1.0
    bit_length: int = 16
    byte_order: str = "little_endian"
    is_signed: bool = True
    raw_params: dict = field(default_factory=dict)


@dataclass
class DBCSignal:
    """Represents a DBC signal."""
    name: str
    start_bit: int
    bit_length: int
    byte_order: int  # 0 = big endian, 1 = little endian
    is_signed: bool
    scale: float
    offset: float
    min_val: float
    max_val: float
    unit: str


@dataclass
class DBCMessage:
    """Represents a DBC message."""
    msg_id: int
    name: str
    dlc: int
    signals: list[DBCSignal] = field(default_factory=list)


# =============================================================================
# TOML Parser and Validator
# =============================================================================

class ConfigParser:
    """Parses and validates TOML configuration."""
    
    MODULE_REQUIRED = ["identifier", "func_grp"]
    MODULE_OPTIONAL = {"rtos_tick_hz": 1000}
    
    SENSOR_COMMON_OPTIONAL = {
        "name": None,
        "type": "analog",
        "offset": 0.0,
        "scale": 1.0,
        "bit_length": 16,
        "byte_order": "little_endian",
        "is_signed": True,
    }
    
    def __init__(self, toml_path: Path):
        self.toml_path = toml_path
        self.errors: list[str] = []
        self.warnings: list[str] = []
    
    def parse(self) -> tuple[ModuleConfig | None, list[SensorConfig]]:
        """Parse TOML file and return validated configuration."""
        try:
            with open(self.toml_path, "rb") as f:
                data = tomllib.load(f)
        except FileNotFoundError:
            self.errors.append(f"Configuration file not found: {self.toml_path}")
            return None, []
        except tomllib.TOMLDecodeError as e:
            self.errors.append(f"TOML parsing error: {e}")
            return None, []
        
        if "module" not in data:
            self.errors.append("Missing [module] section in configuration")
            return None, []
        
        module_data = data["module"]
        module_config = self._parse_module(module_data)
        sensors = self._parse_sensors(module_data.get("sensors", []))
        
        return module_config, sensors
    
    def _parse_module(self, module_data: dict) -> ModuleConfig | None:
        """Parse and validate module configuration."""
        for param in self.MODULE_REQUIRED:
            if param not in module_data:
                self.errors.append(f"Missing required module parameter: '{param}'")
        
        if self.errors:
            return None
        
        func_grp = module_data["func_grp"]
        if isinstance(func_grp, str):
            try:
                func_grp = int(func_grp, 16)
            except ValueError:
                self.errors.append(f"Invalid func_grp hex value: {func_grp}")
                return None
        
        if not 0x0 <= func_grp <= 0xF:
            self.errors.append(f"func_grp must be 0x0 to 0xF, got: {hex(func_grp)}")
        
        return ModuleConfig(
            identifier=module_data["identifier"],
            func_grp=func_grp,
            rtos_tick_hz=module_data.get("rtos_tick_hz", self.MODULE_OPTIONAL["rtos_tick_hz"]),
        )
    
    def _parse_sensors(self, sensors_data: list[dict]) -> list[SensorConfig]:
        """Parse and validate sensor configurations."""
        sensors = []
        
        for i, sensor_data in enumerate(sensors_data):
            sensor_type = sensor_data.get("type", "analog")
            
            # Generate default name if not provided
            name = sensor_data.get("name")
            if name is None:
                name = f"Signal_{i}"
                self.warnings.append(
                    f"Sensor {i}: no 'name' provided, using default '{name}'"
                )
            
            # Validate sensor type exists
            if sensor_type not in SENSOR_ARCHETYPES:
                self.errors.append(
                    f"Sensor {i}: unknown type '{sensor_type}'. "
                    f"Available types: {list(SENSOR_ARCHETYPES.keys())}"
                )
                continue
            
            # Validate sensor-specific parameters
            archetype = SENSOR_ARCHETYPES[sensor_type]
            type_errors = archetype.validate(sensor_data, i)
            self.errors.extend(type_errors)
            
            sensor = SensorConfig(
                name=name,
                sensor_type=sensor_type,
                offset=sensor_data.get("offset", 0.0),
                scale=sensor_data.get("scale", 1.0),
                bit_length=sensor_data.get("bit_length", 16),
                byte_order=sensor_data.get("byte_order", "little_endian"),
                is_signed=sensor_data.get("is_signed", True),
                raw_params=sensor_data,
            )
            sensors.append(sensor)
        
        return sensors
    
    def is_valid(self) -> bool:
        """Check if configuration is valid."""
        return len(self.errors) == 0


# =============================================================================
# DBC Generator
# =============================================================================

class DBCGenerator:
    """Generates DBC files from parsed configuration."""
    
    def __init__(self, module: ModuleConfig, sensors: list[SensorConfig]):
        self.module = module
        self.sensors = sensors
    
    def generate(self) -> str:
        """Generate complete DBC file content."""
        lines = []
        
        # DBC header
        lines.append('VERSION ""')
        lines.append("")
        lines.append("NS_ :")
        lines.append("")
        lines.append("BS_:")
        lines.append("")
        
        # Nodes
        lines.append(f'BU_: {self.module.identifier}')
        lines.append("")
        
        # Generate messages
        messages = self._create_messages()
        for msg in messages:
            lines.append(self._format_message(msg))
            for signal in msg.signals:
                lines.append(self._format_signal(signal))
            lines.append("")
        
        # Comments section
        lines.append("CM_ ")
        lines.append(f'CM_ BU_ {self.module.identifier} "Data acquisition module";')
        for msg in messages:
            lines.append(f'CM_ BO_ {msg.msg_id} "{msg.name} message";')
            for signal in msg.signals:
                lines.append(
                    f'CM_ SG_ {msg.msg_id} {signal.name} "{signal.name} sensor signal";'
                )
        lines.append("")
        
        # Attributes (optional, but good practice)
        lines.append('BA_DEF_ BO_ "GenMsgCycleTime" INT 0 10000;')
        lines.append('BA_DEF_DEF_ "GenMsgCycleTime" 100;')
        lines.append("")
        
        return "\n".join(lines)
    
    def _create_messages(self) -> list[DBCMessage]:
        """Create DBC messages from sensor configuration."""
        messages = []
        
        # Calculate base message ID from func_grp
        # Using extended ID format: func_grp in upper nibble
        base_id = (self.module.func_grp << 24) | 0x100
        
        # Pack signals into messages (8 bytes max per CAN message)
        current_msg_signals: list[DBCSignal] = []
        current_bit_position = 0
        msg_index = 0
        
        for sensor in self.sensors:
            # Get archetype-specific DBC parameters
            archetype = SENSOR_ARCHETYPES.get(sensor.sensor_type)
            dbc_params = archetype.get_dbc_params(sensor.raw_params) if archetype else {}
            
            signal = DBCSignal(
                name=self._sanitize_name(sensor.name),
                start_bit=current_bit_position,
                bit_length=sensor.bit_length,
                byte_order=1 if sensor.byte_order == "little_endian" else 0,
                is_signed=sensor.is_signed,
                scale=sensor.scale,
                offset=sensor.offset,
                min_val=dbc_params.get("min_val", 0),
                max_val=dbc_params.get("max_val", 65535),
                unit=dbc_params.get("unit", ""),
            )
            
            # Check if signal fits in current message
            if current_bit_position + sensor.bit_length > 64:
                # Save current message and start new one
                if current_msg_signals:
                    dlc = (current_bit_position + 7) // 8
                    messages.append(DBCMessage(
                        msg_id=base_id + msg_index,
                        name=f"{self.module.identifier}_Msg{msg_index}",
                        dlc=dlc,
                        signals=current_msg_signals,
                    ))
                    msg_index += 1
                
                current_msg_signals = []
                current_bit_position = 0
                signal.start_bit = 0
            
            current_msg_signals.append(signal)
            current_bit_position += sensor.bit_length
        
        # Don't forget the last message
        if current_msg_signals:
            dlc = (current_bit_position + 7) // 8
            messages.append(DBCMessage(
                msg_id=base_id + msg_index,
                name=f"{self.module.identifier}_Msg{msg_index}",
                dlc=dlc,
                signals=current_msg_signals,
            ))
        
        return messages
    
    def _format_message(self, msg: DBCMessage) -> str:
        """Format a DBC message line."""
        return f"BO_ {msg.msg_id} {msg.name}: {msg.dlc} {self.module.identifier}"
    
    def _format_signal(self, signal: DBCSignal) -> str:
        """Format a DBC signal line."""
        sign_char = "-" if signal.is_signed else "+"
        return (
            f" SG_ {signal.name} : {signal.start_bit}|{signal.bit_length}"
            f"@{signal.byte_order}{sign_char} "
            f"({signal.scale},{signal.offset}) "
            f"[{signal.min_val}|{signal.max_val}] "
            f'"{signal.unit}" Vector__XXX'
        )
    
    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Sanitize name for DBC compatibility."""
        # Replace spaces and special chars with underscores
        sanitized = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
        # Ensure it doesn't start with a number
        if sanitized and sanitized[0].isdigit():
            sanitized = "_" + sanitized
        return sanitized


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate DBC files from TOML configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example TOML configuration:

    [module]
    identifier = "DAQ_Module_1"
    func_grp = 0x1
    rtos_tick_hz = 1000

    [[module.sensors]]
    name = "Engine_Temp"
    type = "thermistor"
    offset = -40.0
    scale = 0.1
    A = 0.001129148
    B = 0.000234125
    C = 0.0000000876741

    [[module.sensors]]
    name = "Voltage_Sense"
    type = "analog"
    scale = 0.001
    min_voltage = 0.0
    max_voltage = 3.3
        """
    )
    parser.add_argument(
        "config",
        type=Path,
        nargs="?",
        default=None,
        help="Path to TOML configuration file"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output DBC file path (default: <config_name>.dbc)"
    )
    parser.add_argument(
        "--list-types",
        action="store_true",
        help="List available sensor types and exit"
    )
    
    args = parser.parse_args()
    
    if args.list_types:
        print("Available sensor types:")
        print("-" * 40)
        for type_name, archetype in SENSOR_ARCHETYPES.items():
            print(f"\n  {type_name}:")
            print(f"    Required params: {archetype.REQUIRED_PARAMS or 'None'}")
            print(f"    Optional params: {list(archetype.OPTIONAL_PARAMS.keys()) or 'None'}")
        return 0
    
    if args.config is None:
        parser.error("config file is required (unless using --list-types)")
    
    # Parse configuration
    config_parser = ConfigParser(args.config)
    module, sensors = config_parser.parse()
    
    # Print warnings
    for warning in config_parser.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    
    # Check for errors
    if not config_parser.is_valid():
        print("Configuration errors:", file=sys.stderr)
        for error in config_parser.errors:
            print(f"  ERROR: {error}", file=sys.stderr)
        return 1
    
    if not sensors:
        print("WARNING: No sensors defined in configuration", file=sys.stderr)
    
    # Generate DBC
    generator = DBCGenerator(module, sensors)
    dbc_content = generator.generate()
    
    # Determine output path
    output_path = args.output
    if output_path is None:
        output_path = args.config.with_suffix(".dbc")
    
    # Write output
    with open(output_path, "w") as f:
        f.write(dbc_content)
    
    print(f"Generated DBC file: {output_path}")
    print(f"  Module: {module.identifier}")
    print(f"  Sensors: {len(sensors)}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

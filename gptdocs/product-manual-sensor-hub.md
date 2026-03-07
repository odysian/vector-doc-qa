Sensor Hub User Manual

Product: Sensor Hub
Model: SH-88
Firmware baseline: 2.4.1
Support team: Field Systems Group
Introduction

The Sensor Hub is a compact aggregation device designed to collect readings from distributed wireless environmental sensors and relay that information to a local control application or remote monitoring console. This manual describes setup, operating limits, maintenance expectations, and common troubleshooting steps for the Model SH-88 platform. The guidance in this document is intended for site technicians, facilities staff, and integrators responsible for installation or routine operation.

The device supports small industrial and commercial deployments where reliability, straightforward maintenance, and predictable operating rules are more important than extensive customization. The SH-88 can be deployed in utility rooms, light manufacturing environments, warehouse zones, lab support spaces, or building automation closets where compatible sensors are in range.
Package Contents

A standard SH-88 package includes:
- 1 Sensor Hub main unit
- 1 power adapter
- 1 wall-mount bracket
- 2 mounting screws
- quick setup insert
- compliance and warranty sheet

Inspect all items before installation. If the enclosure is cracked, ports are bent, or the status LED panel appears loose, do not apply power.
Core Specifications

The operating temp -10°C to 55°C range applies during active use. Storage outside that range is permitted only under the separate storage specification, but startup should occur within the supported operating band. When installed in enclosed cabinets, airflow should be checked to ensure internal temperature does not rise above the maximum.

The hub supports a max paired sensors 32 limit. This total includes active and standby paired devices registered to the hub, even if some sensors are temporarily offline. Large sites should segment deployments across multiple hubs rather than overloading a single unit.

The enclosure carries an ingress rating IP54, which provides limited dust protection and protection against splashing water. The hub should not be submerged or directly exposed to pressurized washdown conditions.

Nominal power draw 18W applies during ordinary operation with a moderate sensor count and standard reporting intervals. Power use may vary slightly based on link activity and peripheral load.
Initial Setup

Before first use, place the unit on a stable surface or install it using the included mount. Connect the power adapter and allow the device to boot fully. On first startup, the hub enters guided configuration mode.

For security during initial provisioning, the default admin PIN 481920 is required the first time an administrator accesses the local setup interface. The PIN should be changed immediately after the first successful login. Do not post the changed code near the device or share it in unsecured communications.

Guided setup includes:
1. language selection
2. local network configuration
3. administrator credential update
4. date and time validation
5. pairing mode activation
6. system naming

If the guided setup process is not completed in time, the setup timeout 12 minutes rule applies and the unit will exit pairing mode to reduce unauthorized provisioning risk. You may restart setup from the front panel menu or the maintenance reset option.
Pairing Sensors

To pair compatible sensors:
1. confirm the hub is powered and in pairing mode
2. place the sensor in discovery state
3. wait for the device to appear in the local pairing list
4. assign a label and zone
5. confirm and save

The hub is designed for efficient discovery of common sensor types, but pairing behavior may vary by radio conditions and battery state. Avoid pairing large batches in areas with heavy interference. If multiple sensors are discovered with similar default names, rename them immediately to avoid confusion during later maintenance.

Remember that the max paired sensors 32 limit is enforced by the device. If the limit has been reached, additional pairing attempts will be rejected until one or more sensors are removed.
Normal Operation

Once configured, the SH-88 continuously gathers readings from paired devices and forwards data according to the site integration method. During routine operation, users mainly interact with the dashboard, summary indicators, and fault notifications.

The front panel status LED provides quick health visibility:
- solid green: normal operation
- blinking blue: pairing mode
- solid amber: maintenance alert
- blinking red: fault condition

A LED fault code F-17 indicates persistent communication inconsistency between the hub and one or more paired devices after the retry threshold has been exceeded. When F-17 appears, inspect sensor placement, recent network changes, and antenna obstruction before escalating support.
Maintenance

Routine upkeep is minimal but important. Dust should be removed from vents and connection points with non-conductive cleaning tools. Mounting points should be inspected for looseness, especially in vibration-prone spaces.

The device requires periodic verification to ensure sensor readings remain aligned with site expectations. The recommended calibration interval 120 days applies to the hub’s validation workflow and associated connected sensor review process. Sites operating in highly variable conditions may adopt a shorter interval if approved by internal quality procedures.

Firmware updates should be staged and tested according to local change control. This manual assumes firmware baseline 2.4.1. Features or menu names may differ slightly on later revisions, though the operating limits in this manual remain the reference for this deployment profile.
Troubleshooting

If the hub does not boot:
- verify power source and adapter connection
- inspect the power indicator
- confirm outlet continuity
- wait 60 seconds and retry

If sensors drop intermittently:
- verify sensor battery health
- inspect line-of-sight obstacles
- reduce interference from nearby equipment
- review whether the site has exceeded practical radio density

If the panel displays LED fault code F-17 repeatedly after reboot and sensor reseating, record the time of occurrence, hub serial reference, and the number of affected sensors before contacting support.
Support and Escalation

For installation problems, repeated faults, unclear setup behavior, or suspected hardware defects, contact the Field Systems Group. When escalating, provide:
- model number
- firmware version
- installation environment
- fault code if present
- number of paired sensors
- approximate ambient temperature

Including the Model SH-88 identifier and current firmware state helps support determine whether the issue is environmental, configuration-related, or hardware-specific.
Operating Summary

Technicians should remember the following critical values during deployment:
- operating temp -10°C to 55°C
- max paired sensors 32
- default admin PIN 481920
- calibration interval 120 days
- ingress rating IP54
- power draw 18W
- setup timeout 12 minutes
- LED fault code F-17
- firmware baseline 2.4.1
- support contact: Field Systems Group

Used correctly, the SH-88 provides a stable and manageable monitoring point for small and mid-sized sensor deployments while keeping setup and maintenance requirements straightforward.

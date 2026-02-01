#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import xml.etree.ElementTree as ET
import sys

pom_file = 'gateway-ha/pom.xml'
tree = ET.parse(pom_file)
root = tree.getroot()

ns = {'maven': 'http://maven.apache.org/POM/4.0.0'}
dependencies = root.find('.//maven:dependencies', ns)

if dependencies is None:
    print(f"ERROR: Could not find dependencies section in {pom_file}")
    sys.exit(1)

h2_exists = False
for dep in dependencies.findall('.//maven:dependency', ns):
    group_id = dep.find('maven:groupId', ns)
    artifact_id = dep.find('maven:artifactId', ns)
    if group_id is not None and artifact_id is not None:
        if group_id.text == 'com.h2database' and artifact_id.text == 'h2':
            h2_exists = True
            version = dep.find('maven:version', ns)
            if version is not None:
                version.text = '2.2.224'
            else:
                version_elem = ET.SubElement(dep, '{http://maven.apache.org/POM/4.0.0}version')
                version_elem.text = '2.2.224'
            print(f"INFO: H2 dependency already exists, updating version to 2.2.224")
            break

if not h2_exists:
    # Criar elementos com namespace correto
    h2_dep = ET.SubElement(dependencies, '{http://maven.apache.org/POM/4.0.0}dependency')
    group_id = ET.SubElement(h2_dep, '{http://maven.apache.org/POM/4.0.0}groupId')
    group_id.text = 'com.h2database'
    artifact_id = ET.SubElement(h2_dep, '{http://maven.apache.org/POM/4.0.0}artifactId')
    artifact_id.text = 'h2'
    version = ET.SubElement(h2_dep, '{http://maven.apache.org/POM/4.0.0}version')
    version.text = '2.2.224'
    # Garantir que o H2 seja incluído com scope compile (padrão)
    print(f"SUCCESS: Added H2 dependency to {pom_file}")

# Garantir que o H2 tenha scope compile (ou nenhum scope, que é o padrão)
for dep in dependencies.findall('.//maven:dependency', ns):
    group_id = dep.find('maven:groupId', ns)
    artifact_id = dep.find('maven:artifactId', ns)
    if group_id is not None and artifact_id is not None:
        if group_id.text == 'com.h2database' and artifact_id.text == 'h2':
            scope = dep.find('maven:scope', ns)
            if scope is not None and scope.text != 'compile':
                scope.text = 'compile'
                print(f"INFO: Updated H2 scope to compile")
            elif scope is None:
                # Scope padrão é compile, não precisa adicionar
                pass
            break

ET.register_namespace('', 'http://maven.apache.org/POM/4.0.0')
tree.write(pom_file, encoding='utf-8', xml_declaration=True)
print(f"SUCCESS: Updated {pom_file}")


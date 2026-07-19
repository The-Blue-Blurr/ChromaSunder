#!/bin/bash

flatpak-builder --force-clean --user --install build-dir flatpak/io.github.the_blue_blurr.ChromaSunder.yml

sleep 1

flatpak run io.github.the_blue_blurr.ChromaSunder

working in combination with dns spoofing and port forwarding

following configuration is for openwrt.

# 1) DNAT: Redirect [INTERNAL_FIXED_IP_HYPONTECH] -> 47.91.250.143:51100 to Docker host:51100
  uci add firewall redirect
  uci set firewall.@redirect[-1].name='Hypontech-51100-DNAT'
  uci set firewall.@redirect[-1].src='lan'
  uci set firewall.@redirect[-1].src_ip='[INTERNAL_FIXED_IP_HYPONTECH]'
  uci set firewall.@redirect[-1].src_dip='47.91.250.143'
  uci set firewall.@redirect[-1].proto='tcp'
  uci set firewall.@redirect[-1].src_dport='51100'
  uci set firewall.@redirect[-1].dest='lan'
  uci set firewall.@redirect[-1].dest_ip='[INTERNAL_FIX_IP_DOCKER]'
  uci set firewall.@redirect[-1].dest_port='51100'
  uci set firewall.@redirect[-1].target='DNAT'
  uci set firewall.@redirect[-1].reflection='0'
  
# 2) Hairpin SNAT/Masquerade: Force Docker replies back through OpenWrt
  uci add firewall nat
  uci set firewall.@nat[-1].name='Hypontech-51100-Hairpin'
  uci set firewall.@nat[-1].src='lan'
  uci set firewall.@nat[-1].src_ip='[INTERNAL_FIXED_IP_HYPONTECH]'
  uci set firewall.@nat[-1].dest_ip='[INTERNAL_FIX_IP_DOCKER]'
  uci set firewall.@nat[-1].dest_port='51100'
  uci set firewall.@nat[-1].proto='tcp'
  uci set firewall.@nat[-1].target='MASQUERADE'
  
  uci commit firewall
  /etc/init.d/firewall restart

# 3) Firewallk rule OpenWrt to be take hypontech 100% offline
uci add firewall rule
uci set firewall.@rule[-1].name='Block-Hypontech-WAN'
uci set firewall.@rule[-1].src='lan'
uci add_list firewall.@rule[-1].src_mac='XX:XX:XX:XX:XX:XX'  # Replace with dongle MAC
uci set firewall.@rule[-1].dest='wan'
uci set firewall.@rule[-1].proto='all'
uci set firewall.@rule[-1].target='REJECT'
uci commit firewall
/etc/init.d/firewall restart

# 4) Docker setup

once this is done, put all the file into the folder of your choice.
edit the docker compose to match the correct value for:

MQTT_HOST: "MQTT_HOST"   # Your Home Assistant / Mosquitto LAN IP (or 127.0.0.1 if same host)
MQTT_PORT: MQTT_PORT
MQTT_USER: "MQTT_USER"
MQTT_PASS: "MQTT_PASS"

then run the command
  sudo docker compose up -d --build
  sudo docker compose logs -f
   
# 5) Connection established

This should give you the following output:

hypontech-bridge  | Listening on 0.0.0.0:51100 -> MQTT x.x.x.x:1883
hypontech-bridge  | [+] Stick connected from ('x.x.x.x', 52354)
hypontech-bridge  | [*] ('x.x.x.x', 52354) Login OK
hypontech-bridge  | [+] Published HA MQTT discovery for S300-----------
hypontech-bridge  | [.] ('x.x.x.x', 52354) Keepalive seq=cd

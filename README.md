working in combination with dns spoofing and port forwarding

on openwrt add those rules to redirect flow from hypontech to docker
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

you need also to define a firewall rull to prevent hypontech to reach internet.

once this is done, put all the file into the folder of your choice and run the following:

  sudo docker compose up -d --build
  sudo docker compose logs -f
   
that will give you some output like this:

hypontech-bridge  | Listening on 0.0.0.0:51100 -> MQTT x.x.x.x:1883
hypontech-bridge  | [+] Stick connected from ('x.x.x.x', 52354)
hypontech-bridge  | [*] ('x.x.x.x', 52354) Login OK
hypontech-bridge  | [+] Published HA MQTT discovery for S300-----------
hypontech-bridge  | [.] ('x.x.x.x', 52354) Keepalive seq=cd

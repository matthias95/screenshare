# screenshare
Simple python package for streaming your screen to another device in the local network.

# install 
`python3 -m pip install screenshare`

# usage 
On the receiving device (display server):   
`python3 -m screenshare`
  
On the sending device (streaming server):   
`python3 -m screenshare --host <ip>`

Where `<ip>` is the IP adress or DNS name of the display server.

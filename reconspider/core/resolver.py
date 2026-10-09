"""Filter the actual address stream Twisted uses to establish each connection."""

from twisted.internet.interfaces import IHostnameResolver, IResolutionReceiver
from zope.interface import implementer

from reconspider.core.scope import public_address


@implementer(IResolutionReceiver)
class SafeReceiver:
    def __init__(self, receiver, allow_local=False):
        self.receiver = receiver
        self.allow_local = allow_local
        self.addresses = []
        self.blocked = False

    def resolutionBegan(self, resolution):
        self.receiver.resolutionBegan(resolution)

    def addressResolved(self, address):
        if self.allow_local or public_address(address.host):
            self.addresses.append(address)
        else:
            self.blocked = True

    def resolutionComplete(self):
        # Withhold the entire answer if it contains any unsafe address.
        if not self.blocked:
            for address in self.addresses:
                self.receiver.addressResolved(address)
        self.receiver.resolutionComplete()


@implementer(IHostnameResolver)
class SafeResolver:
    def __init__(self, reactor, allow_local=False):
        self.reactor = reactor
        self.original = reactor.nameResolver
        self.allow_local = allow_local

    @classmethod
    def from_crawler(cls, crawler, reactor):
        return cls(reactor, crawler.settings.getbool("RECON_ALLOW_LOCAL"))

    def install_on_reactor(self):
        self.reactor.installNameResolver(self)

    def resolveHostName(
        self, receiver, hostName, portNumber=0, addressTypes=None, transportSemantics="TCP"
    ):
        return self.original.resolveHostName(
            SafeReceiver(receiver, self.allow_local),
            hostName,
            portNumber,
            addressTypes,
            transportSemantics,
        )

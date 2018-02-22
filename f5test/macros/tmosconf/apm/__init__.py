'''
Created on Mar 17, 2016

@author: jono
'''
from ..scaffolding import Stamp, Literal
import logging
from ....base import enum
from ....utils.parsers import tmsh
from ....utils.parsers.tmsh import RawEOL

LOG = logging.getLogger(__name__)


class ClientPackaging(Stamp):
    TMSH = """
        apm swg-scheme %(key)s { }
        """

    def __init__(self, name='malware'):
        self.name = name
        super(ClientPackaging, self).__init__()

    def tmsh(self, obj):
        key = self.folder.SEPARATOR.join((self.folder.key(), self.name))
        obj.rename_key('apm swg-scheme %(key)s', key=key)
        return key, obj


class UrlFilter(Stamp):
    TMSH = """
        apm url-filter %(key)s {
            allowed-categories { /Common/Nutrition /Common/Adult_Material /Common/Business_and_Economy /Common/Education /Common/Government /Common/News_and_Media /Common/Religion /Common/Society_and_Lifestyles /Common/Special_Events /Common/Information_Technology /Common/Abortion /Common/Advocacy_Groups /Common/Entertainment /Common/Gambling /Common/Games /Common/Illegal_or_Questionable /Common/Job_Search /Common/Shopping /Common/Sports /Common/Tasteless /Common/Travel /Common/Vehicles /Common/Violence /Common/Weapons /Common/Drugs /Common/Militancy_and_Extremist /Common/Intolerance /Common/Health /Common/Website_Translation /Common/Advertisements /Common/User-Defined /Common/Nudity /Common/Adult_Content /Common/Sex /Common/Financial_Data_and_Services /Common/Cultural_Institutions /Common/Media_File_Download /Common/Military /Common/Political_Organizations /Common/General_Email /Common/Proxy_Avoidance /Common/Search_Engines_and_Portals /Common/Web_Hosting /Common/Web_Chat /Common/Hacking /Common/Alternative_Journals /Common/Non-Traditional_Religions /Common/Traditional_Religions /Common/Restaurants_and_Dining /Common/Gay_or_Lesbian_or_Bisexual_Interest /Common/Personals_and_Dating /Common/Alcohol_and_Tobacco /Common/Prescribed_Medications /Common/Abused_Drugs /Common/Internet_Communication /Common/Pro-Choice /Common/Pro-Life /Common/Sex_Education /Common/Lingerie_and_Swimsuit /Common/Online_Brokerage_and_Trading /Common/Educational_Institutions /Common/Instant_Messaging /Common/Application_and_Software_Download /Common/Pay-to-Surf /Common/Internet_Auctions /Common/Real_Estate /Common/Hobbies /Common/Sport_Hunting_and_Gun_Clubs /Common/Internet_Telephony /Common/Streaming_Media /Common/Productivity /Common/Marijuana /Common/Message_Boards_and_Forums /Common/Personal_Network_Storage_and_Backup /Common/Internet_Radio_and_TV /Common/Peer-to-Peer_File_Sharing /Common/Bandwidth /Common/Social_Networking /Common/Educational_Materials /Common/Reference_Materials /Common/Social_Organizations /Common/Service_and_Philanthropic_Organizations /Common/Social_and_Affiliation_Organizations /Common/Professional_and_Worker_Organizations /Common/Security /Common/Malicious_Web_Sites /Common/Computer_Security /Common/Miscellaneous /Common/Web_Infrastructure /Common/Web_Images /Common/Private_IP_Addresses /Common/Content_Delivery_Networks /Common/Dynamic_Content /Common/Network_Errors /Common/Uncategorized /Common/Spyware /Common/File_Download_Servers /Common/Phishing_and_Other_Frauds /Common/Keyloggers /Common/Potentially_Unwanted_Software /Common/Bot_Networks /Common/Extended_Protection /Common/Elevated_Exposure /Common/Emerging_Exploits /Common/Suspicious_Content /Common/Organizational_Email /Common/Text_and_Media_Messaging /Common/Web_and_Email_Spam /Common/Web_Collaboration /Common/Parked_Domain /Common/Hosted_Business_Applications /Common/Blogs_and_Personal_Sites /Common/Malicious_Embedded_Link /Common/Malicious_Embedded_iFrame /Common/Suspicious_Embedded_Link /Common/Surveillance /Common/Educational_Video /Common/Entertainment_Video /Common/Viral_Video /Common/Dynamic_DNS /Common/Potentially_Exploited_Documents /Common/Mobile_Malware /Common/Unauthorized_Mobile_Marketplaces /Common/Custom-Encrypted_Uploads /Common/Files_Containing_Passwords /Common/Advanced_Malware_Command_and_Control /Common/Advanced_Malware_Payloads /Common/Compromised_Websites /Common/Newly_Registered_Websites /Common/Collaboration_-_Office /Common/Office_-_Mail /Common/Office_-_Drive /Common/Office_-_Documents /Common/Office_-_Apps /Common/Web_Analytics /Common/Web_and_Email_Marketing /Common/Social_Web_-_Facebook /Common/LinkedIn_Updates /Common/LinkedIn_Mail /Common/LinkedIn_Connections /Common/LinkedIn_Jobs /Common/Facebook_Posting /Common/Facebook_Commenting /Common/Facebook_Friends /Common/Facebook_Photo_Upload /Common/Facebook_Mail /Common/Facebook_Events /Common/YouTube_Commenting /Common/YouTube_Video_Upload /Common/Facebook_Apps /Common/Facebook_Chat /Common/Facebook_Questions /Common/Facebook_Video_Upload /Common/Facebook_Groups /Common/Twitter_Posting /Common/Twitter_Mail /Common/Twitter_Follow /Common/YouTube_Sharing /Common/Facebook_Games /Common/Social_Web_-_YouTube /Common/Social_Web_-_Twitter /Common/Social_Web_-_LinkedIn /Common/Social_Web_-_Various /Common/Classifieds_Posting /Common/Blog_Posting /Common/Blog_Commenting }
            blocked-categories { }
        }
        """

    def __init__(self, name='malware', allowed_cats=None, blocked_cats=None):
        self.name = name
        self.allowed_cats = allowed_cats or []
        self.blocked_cats = blocked_cats or []
        super(UrlFilter, self).__init__()

    def tmsh(self, obj):
        key = self.get_full_path()
        print key
        value = obj.rename_key('apm url-filter %(key)s', key=key)
        for category in self.blocked_cats:
            value['blocked-categories'].append(category.get_full_path())
        return key, obj


